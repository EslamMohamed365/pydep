from __future__ import annotations

from pathlib import Path

from base import Ecosystem, Package, RegistryPackageInfo, EnvInfo


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
        return False, "Not implemented"

    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        return False, "Not implemented"

    async def remove(
        self, package: str, source: str, group: str | None = None
    ) -> tuple[bool, str]:
        return False, "Not implemented"

    async def sync(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def lock(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def create_env(self) -> tuple[bool, str]:
        return False, "Not implemented"

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
