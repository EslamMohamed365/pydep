from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

import requests

from base import Ecosystem, Package, DepSource, RegistryPackageInfo, EnvInfo

# === Registry Constants ===
GO_PROXY = "https://proxy.golang.org"


# === Helper Functions ===


async def _get_go_module_info(module: str) -> dict | None:
    """Fetch module info from Go proxy."""
    url = f"{GO_PROXY}/{module}/@latest"
    try:
        resp = await asyncio.to_thread(requests.get, url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None


async def _list_go_versions(module: str) -> list[str]:
    """List all versions of a Go module."""
    url = f"{GO_PROXY}/{module}/@v/list"
    try:
        resp = await asyncio.to_thread(requests.get, url, timeout=10)
        if resp.status_code == 200:
            return resp.text.strip().splitlines()
    except requests.RequestException:
        pass
    return []


async def _get_go_version() -> str:
    """Get Go version."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "go",
            "version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        match = re.search(r"go(\d+\.\d+\.\d+)", out.decode())
        return match.group(1) if match else ""
    except Exception:
        return ""


# === Package Manager ===


class GoManager:
    """Wrapper around go CLI."""

    def __init__(self):
        self._go = shutil.which("go")

    async def _run(self, *args: str) -> tuple[int, str, str]:
        if self._go is None:
            return 1, "", "go not found"
        proc = await asyncio.create_subprocess_exec(
            self._go,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

    async def init(self, module_name: str) -> tuple[bool, str]:
        code, out, err = await self._run("mod", "init", module_name)
        return code == 0, err or out

    async def get(self, spec: str) -> tuple[bool, str]:
        # spec format: module@version
        code, out, err = await self._run("get", spec)
        return code == 0, err or out

    async def remove(self, module: str) -> tuple[bool, str]:
        # go get module@none removes, then go mod tidy cleans up
        code1, _, err1 = await self._run("get", f"{module}@none")
        code2, _, err2 = await self._run("mod", "tidy")
        success = code1 == 0 and code2 == 0
        return success, err1 or err2

    async def tidy(self) -> tuple[bool, str]:
        code, out, err = await self._run("mod", "tidy")
        return code == 0, err or out

    async def download(self) -> tuple[bool, str]:
        code, out, err = await self._run("mod", "download")
        return code == 0, err or out


# === Ecosystem ===


class GoEcosystem(Ecosystem):
    name = "go"
    display_name = "Go"
    source_colors = {
        "go.mod": "#7dcfff",
        "go.sum": "#565f89",
    }
    source_abbrevs = {
        "go.mod": "go.mod",
    }

    def __init__(self) -> None:
        self._go_mgr = GoManager()

    def detect(self, path: Path) -> bool:
        return (path / "go.mod").exists()

    # === Parsing ===

    async def _parse_go_mod(self, path: Path) -> list[tuple[str, str, bool]]:
        """Parse go.mod for require statements."""
        if not path.exists():
            return []

        deps = []
        content = path.read_text()
        in_require = False

        for line in content.splitlines():
            line = line.strip()

            if line.startswith("require ("):
                in_require = True
                continue
            elif line == ")" and in_require:
                in_require = False
                continue

            if in_require or line.startswith("require "):
                if line.startswith("require "):
                    line = line[8:].strip()

                # Parse "module v1.2.3" or "module v1.2.3 // indirect"
                parts = line.split()
                if len(parts) >= 2:
                    module = parts[0]
                    version = parts[1]
                    is_indirect = "// indirect" in line
                    deps.append((module, version, is_indirect))

        return deps

    async def _parse_go_sum(self, path: Path) -> dict[str, str]:
        """Parse go.sum for module hashes (optional)."""
        if not path.exists():
            return {}
        # go.sum format: module version hash
        result = {}
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                module = parts[0]
                version = parts[1]
                result[module] = version
        return result

    async def load_dependencies(self, path: Path) -> list[Package]:
        """Scan for Go module dependencies."""
        deps = await self._parse_go_mod(path / "go.mod")

        merged: dict[str, Package] = {}
        for module, version, is_indirect in deps:
            source_label = "indirect" if is_indirect else "main"
            if module not in merged:
                merged[module] = Package(
                    name=module,
                    sources=[DepSource(file=source_label, specifier=version)],
                    installed_version=version,
                    ecosystem=self,
                )
            else:
                merged[module].sources.append(
                    DepSource(file=source_label, specifier=version)
                )

        return sorted(merged.values(), key=lambda p: p.name.lower())

    # === Package Manager ===

    async def init_project(self, path: Path) -> tuple[bool, str]:
        # Use directory name as module name
        module_name = path.name
        return await self._go_mgr.init(module_name)

    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        # spec is module@version or module
        if "@" not in spec:
            spec = f"{spec}@latest"
        return await self._go_mgr.get(spec)

    async def remove(
        self, package: str, source: str, group: str | None = None
    ) -> tuple[bool, str]:
        return await self._go_mgr.remove(package)

    async def sync(self) -> tuple[bool, str]:
        return await self._go_mgr.tidy()

    async def lock(self) -> tuple[bool, str]:
        return await self._go_mgr.download()

    async def create_env(self) -> tuple[bool, str]:
        # Go doesn't have venvs - modules are global
        return True, "Go modules don't require environment creation"

    # === Registry ===

    async def validate_package(
        self, name: str, version: str | None = None
    ) -> tuple[bool, str, str]:
        data = await _get_go_module_info(name)
        if not data:
            return False, f"Module '{name}' not found on proxy.golang.org", ""

        latest = data.get("Version", "")
        if version and version != latest:
            versions = await _list_go_versions(name)
            if version not in versions:
                return False, f"Version {version} not found", ""

        return True, "", latest

    async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
        results = {}
        for name in names:
            data = await _get_go_module_info(name)
            if data:
                results[name] = data.get("Version", "")
        return results

    async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
        # Go doesn't have a good search API - return empty for now
        # Could add pkg.go.dev scraping in the future
        return []

    async def fetch_package_metadata(self, name: str) -> dict[str, str]:
        data = await _get_go_module_info(name)
        if not data:
            return {}

        return {
            "name": data.get("Name", ""),
            "version": data.get("Version", ""),
            "description": data.get("Summary", ""),
            "license": data.get("License", ""),
            "homepage": data.get("Homepage", ""),
        }

    async def get_package_requires(self, name: str) -> list[str]:
        # Go modules don't have easy introspection without downloading
        return []

    # === Environment ===

    async def get_env_info(self) -> EnvInfo:
        go_ver = await _get_go_version() or "not found"

        return EnvInfo(
            language_name="Go",
            language_version=go_ver,
            tool_name="go",
            tool_version=go_ver,
            env_label="GOPATH",
            env_exists=True,  # Go modules don't need explicit env
        )

    def get_docs_url(self, name: str) -> str:
        return f"https://pkg.go.dev/{name}"
