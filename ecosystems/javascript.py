from __future__ import annotations

from pathlib import Path

from base import Ecosystem, Package, RegistryPackageInfo, EnvInfo


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

    def detect(self, path: Path) -> bool:
        return (path / "package.json").exists()

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
        return EnvInfo("Node.js", "", "npm", "", "node_modules", False)

    def get_docs_url(self, name: str) -> str:
        return f"https://www.npmjs.com/package/{name}"
