from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import requests

from base import Ecosystem, Package, DepSource, RegistryPackageInfo, EnvInfo

# === Registry Constants ===
NPM_REGISTRY = "https://registry.npmjs.org"


# === Helper Functions ===


async def _get_npm_json(name: str) -> dict | None:
    """Fetch package metadata from npm registry."""
    url = f"{NPM_REGISTRY}/{name}"
    try:
        resp = await asyncio.to_thread(requests.get, url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None


async def _search_npm(query: str) -> list[dict]:
    """Search npm registry."""
    url = f"{NPM_REGISTRY}/-/v1/search"
    params = {"text": query, "size": 20}
    try:
        resp = await asyncio.to_thread(requests.get, url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("objects", [])
    except requests.RequestException:
        pass
    return []


async def _get_node_version() -> str:
    """Get Node.js version."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "node",
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        return out.decode().strip()
    except Exception:
        return ""


async def _get_npm_version() -> str:
    """Get npm version."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "npm",
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        return out.decode().strip()
    except Exception:
        return ""


# === Package Manager ===


class NpmManager:
    """Wrapper around npm CLI."""

    def __init__(self):
        self._npm = shutil.which("npm")

    async def _run(self, *args: str) -> tuple[int, str, str]:
        if self._npm is None:
            return 1, "", "npm not found"
        proc = await asyncio.create_subprocess_exec(
            self._npm,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

    async def init(self, path: Path) -> tuple[bool, str]:
        code, out, err = await self._run("init", "-y")
        return code == 0, err or out

    async def install(self, spec: str, dev: bool = False) -> tuple[bool, str]:
        args = ["install", spec]
        if dev:
            args.insert(1, "--save-dev")
        code, out, err = await self._run(*args)
        return code == 0, err or out

    async def uninstall(self, pkg: str) -> tuple[bool, str]:
        code, out, err = await self._run("uninstall", pkg)
        return code == 0, err or out

    async def update(self, spec: str) -> tuple[bool, str]:
        code, out, err = await self._run("install", spec)
        return code == 0, err or out


# === Ecosystem ===


class JavaScriptEcosystem(Ecosystem):
    name = "javascript"
    display_name = "JavaScript"
    source_colors = {
        "package.json": "#9ece6a",
        "package-lock.json": "#565f89",
        "node_modules": "#565f89",
    }
    source_abbrevs = {
        "package.json": "pkg.json",
    }

    def __init__(self) -> None:
        self._npm_mgr = NpmManager()

    def detect(self, path: Path) -> bool:
        return (path / "package.json").exists()

    # === Parsing ===

    async def _parse_package_json(self, path: Path) -> list[tuple[str, str, str]]:
        """Parse package.json dependencies."""
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
        except Exception:
            return []
        deps = []
        for group in [
            "dependencies",
            "devDependencies",
            "peerDependencies",
            "optionalDependencies",
        ]:
            if group in data:
                for name, spec in data[group].items():
                    deps.append((name, spec, group))
        return deps

    async def _parse_package_lock(self, path: Path) -> dict[str, str]:
        """Parse package-lock.json for installed versions."""
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text())
        except Exception:
            return {}
        result = {}
        packages = data.get("packages", {})
        for pkg_path, info in packages.items():
            if pkg_path == "":
                continue
            if "node_modules/" in pkg_path:
                name = pkg_path.split("node_modules/")[-1]
                if "/" in name:
                    name = name.split("/")[0]
                version = info.get("version", "")
                if name and version:
                    result[name] = version
        if not result:
            deps = data.get("dependencies", {})
            for name, info in deps.items():
                version = info.get("version", "")
                if version:
                    result[name] = version
        return result

    async def load_dependencies(self, path: Path) -> list[Package]:
        """Scan for JavaScript dependencies."""
        deps = await self._parse_package_json(path / "package.json")
        lock_versions = await self._parse_package_lock(path / "package-lock.json")

        merged: dict[str, Package] = {}
        for name, spec, group in deps:
            if name not in merged:
                installed = lock_versions.get(name, "")
                merged[name] = Package(
                    name=name,
                    sources=[DepSource(file=group, specifier=spec)],
                    installed_version=installed,
                    ecosystem=self,
                )
            else:
                merged[name].sources.append(DepSource(file=group, specifier=spec))

        return sorted(merged.values(), key=lambda p: p.name.lower())

    # === Package Manager ===

    async def init_project(self, path: Path) -> tuple[bool, str]:
        return await self._npm_mgr.init(path)

    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        dev = group == "dev"
        return await self._npm_mgr.install(spec, dev=dev)

    async def remove(
        self, package: str, source: str, group: str | None = None
    ) -> tuple[bool, str]:
        return await self._npm_mgr.uninstall(package)

    async def sync(self) -> tuple[bool, str]:
        return await self._npm_mgr.install("")

    async def lock(self) -> tuple[bool, str]:
        return True, "package-lock.json auto-generated"

    async def create_env(self) -> tuple[bool, str]:
        return True, "node_modules created on install"

    # === Registry ===

    async def validate_package(
        self, name: str, version: str | None = None
    ) -> tuple[bool, str, str]:
        data = await _get_npm_json(name)
        if not data:
            return False, f"Package '{name}' not found on npm", ""
        latest = data.get("dist-tags", {}).get("latest", "")
        if version and version not in data.get("versions", {}):
            return False, f"Version {version} not found", ""
        return True, "", latest

    async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
        results = {}
        for name in names:
            data = await _get_npm_json(name)
            if data:
                results[name] = data.get("dist-tags", {}).get("latest", "")
        return results

    async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
        results = await _search_npm(query)
        return [
            RegistryPackageInfo(
                name=r.get("package", {}).get("name", ""),
                latest_version=r.get("package", {}).get("version", ""),
                description=r.get("package", {}).get("description", ""),
            )
            for r in results
        ]

    async def fetch_package_metadata(self, name: str) -> dict[str, str]:
        data = await _get_npm_json(name)
        if not data:
            return {}
        latest = data.get("dist-tags", {}).get("latest", "")
        version_data = data.get("versions", {}).get(latest, {})
        return {
            "name": data.get("name", ""),
            "version": latest,
            "description": data.get("description", ""),
            "license": version_data.get("license", ""),
            "homepage": data.get("homepage", ""),
            "author": str(data.get("author", {})),
        }

    async def get_package_requires(self, name: str) -> list[str]:
        data = await _get_npm_json(name)
        if not data:
            return []
        latest = data.get("dist-tags", {}).get("latest", "")
        version_data = data.get("versions", {}).get(latest, {})
        deps = version_data.get("dependencies", {})
        return list(deps.keys()) if deps else []

    # === Environment ===

    async def get_env_info(self) -> EnvInfo:
        node_ver = await _get_node_version() or "not found"
        npm_ver = await _get_npm_version() or "not found"
        nm_exists = Path("node_modules").exists()
        return EnvInfo(
            language_name="Node.js",
            language_version=node_ver,
            tool_name="npm",
            tool_version=npm_ver,
            env_label="node_modules",
            env_exists=nm_exists,
        )

    def get_docs_url(self, name: str) -> str:
        return f"https://www.npmjs.com/package/{name}"
