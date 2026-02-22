from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from base import Ecosystem, Package, RegistryPackageInfo, EnvInfo


class PackageManager:
    """Async wrapper around **uv** project-level commands.

    Every public method runs ``uv`` in a subprocess and returns
    ``(success, output)``.
    """

    def __init__(self) -> None:
        self._uv = shutil.which("uv")
        if self._uv is None:
            raise RuntimeError(
                "'uv' is not installed or not on your PATH.\n"
                "Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh"
            )

    async def _run(self, *args: str) -> tuple[bool, str]:
        """Run a ``uv`` command and capture combined output."""
        cmd = [self._uv, *args]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = (stdout or b"").decode() + (stderr or b"").decode()
        return proc.returncode == 0, output.strip()

    async def init_project(self) -> tuple[bool, str]:
        """Bootstrap a minimal ``pyproject.toml`` via ``uv init --bare``."""
        return await self._run("init", "--bare")

    async def add(
        self,
        package: str,
        version: str | None = None,
        constraint: str = "==",
        group: str | None = None,
    ) -> tuple[bool, str]:
        """Add or update a dependency."""
        args: list[str] = ["add"]
        if group and group != "main":
            args.extend(["--group", group])
        if version:
            spec = f"{package}{constraint}{version}"
        else:
            spec = package
        args.append(spec)
        return await self._run(*args)

    async def remove(self, package: str) -> tuple[bool, str]:
        """Remove a dependency from the project."""
        return await self._run("remove", package)

    async def remove_from_group(self, package: str, group: str) -> tuple[bool, str]:
        """Remove a dependency from an optional-dependencies group."""
        return await self._run("remove", "--group", group, package)

    async def pip_uninstall(self, package: str) -> tuple[bool, str]:
        """Uninstall a package from the active virtual environment."""
        return await self._run("pip", "uninstall", package)

    async def create_venv(self) -> tuple[bool, str]:
        """Create a virtual environment via ``uv venv``."""
        return await self._run("venv")

    async def sync(self) -> tuple[bool, str]:
        """Run ``uv sync``."""
        return await self._run("sync")

    async def lock(self) -> tuple[bool, str]:
        """Run ``uv lock``."""
        return await self._run("lock")


class PythonEcosystem(Ecosystem):
    name = "python"
    display_name = "Python"
    source_colors = {
        "pyproject.toml": "#bb9af7",
        "requirements.txt": "#7dcfff",
        "setup.py": "#e0af02",
        "setup.cfg": "#e0af02",
        "Pipfile": "#9ece6a",
        "venv": "#565f89",
    }
    source_abbrevs = {
        "pyproject.toml": "pyproj",
        "requirements.txt": "reqs",
    }

    def __init__(self) -> None:
        try:
            self._pkg_mgr = PackageManager()
        except RuntimeError:
            self._pkg_mgr = None

    def detect(self, path: Path) -> bool:
        files = [
            "pyproject.toml",
            "requirements.txt",
            "setup.py",
            "setup.cfg",
            "Pipfile",
        ]
        return any((path / f).exists() for f in files)

    async def load_dependencies(self, path: Path) -> list[Package]:
        return []

    async def init_project(self, path: Path) -> tuple[bool, str]:
        if self._pkg_mgr is None:
            return False, "uv not installed"
        return await self._pkg_mgr.init_project()

    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        if self._pkg_mgr is None:
            return False, "uv not installed"
        return await self._pkg_mgr.add(spec)

    async def remove(
        self, package: str, source: str, group: str | None = None
    ) -> tuple[bool, str]:
        if self._pkg_mgr is None:
            return False, "uv not installed"
        return await self._pkg_mgr.remove(package)

    async def sync(self) -> tuple[bool, str]:
        if self._pkg_mgr is None:
            return False, "uv not installed"
        return await self._pkg_mgr.sync()

    async def lock(self) -> tuple[bool, str]:
        if self._pkg_mgr is None:
            return False, "uv not installed"
        return await self._pkg_mgr.lock()

    async def create_env(self) -> tuple[bool, str]:
        if self._pkg_mgr is None:
            return False, "uv not installed"
        return await self._pkg_mgr.create_venv()

    async def validate_package(
        self, name: str, version: str | None = None
    ) -> tuple[bool, str, str]:
        return False, "Not implemented", ""

    async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
        return {}

    async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
        return []

    async def fetch_package_metadata(self, name: str) -> dict[str, str]:
        return {}

    async def get_package_requires(self, name: str) -> list[str]:
        return []

    async def get_env_info(self) -> EnvInfo:
        return EnvInfo("Python", "", "uv", "", ".venv", False)

    def get_docs_url(self, name: str) -> str:
        return f"https://pypi.org/project/{name}/"
