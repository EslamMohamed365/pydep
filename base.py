from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DepSource:
    """One place a dependency was declared."""

    file: str
    specifier: str


@dataclass
class Package:
    """Aggregated dependency across all sources."""

    name: str
    sources: list[DepSource]
    installed_version: str
    ecosystem: Ecosystem | None = None


@dataclass
class RegistryPackageInfo:
    """Metadata from package registry."""

    name: str
    latest_version: str
    description: str
    license: str | None = None
    homepage: str | None = None
    author: str | None = None
    requires: str | None = None


@dataclass
class EnvInfo:
    """Environment information for an ecosystem."""

    language_name: str
    language_version: str
    tool_name: str
    tool_version: str
    env_label: str
    env_exists: bool


class Ecosystem(ABC):
    """Abstract base for package ecosystems (Python, JavaScript, Go, etc.)."""

    name: str
    display_name: str
    source_colors: dict[str, str]
    source_abbrevs: dict[str, str]

    @abstractmethod
    def detect(self, path: Path) -> bool:
        """Return True if this ecosystem's files exist in `path`."""

    @abstractmethod
    async def load_dependencies(self, path: Path) -> list[Package]:
        """Scan `path` for all dependency sources, return merged list."""

    @abstractmethod
    async def init_project(self, path: Path) -> tuple[bool, str]:
        """Initialize a new project. Returns (success, message)."""

    @abstractmethod
    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        """Add a package. Returns (success, message)."""

    @abstractmethod
    async def remove(
        self, package: str, source: str, group: str | None = None
    ) -> tuple[bool, str]:
        """Remove a package. Returns (success, message)."""

    @abstractmethod
    async def sync(self) -> tuple[bool, str]:
        """Sync dependencies. Returns (success, message)."""

    @abstractmethod
    async def lock(self) -> tuple[bool, str]:
        """Lock dependencies. Returns (success, message)."""

    @abstractmethod
    async def create_env(self) -> tuple[bool, str]:
        """Create environment/venv. Returns (success, message)."""

    @abstractmethod
    async def validate_package(
        self, name: str, version: str | None = None
    ) -> tuple[bool, str, str]:
        """Validate package exists on registry. Returns (valid, error, resolved_version)."""

    @abstractmethod
    async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
        """Fetch latest version for each package name. Returns {name: version}."""

    @abstractmethod
    async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
        """Search registry for packages matching query."""

    @abstractmethod
    async def fetch_package_metadata(self, name: str) -> dict[str, str]:
        """Fetch full metadata for a package."""

    @abstractmethod
    async def get_package_requires(self, name: str) -> list[str]:
        """Get list of dependencies for a package."""

    @abstractmethod
    async def get_env_info(self) -> EnvInfo:
        """Get environment information."""

    @abstractmethod
    def get_docs_url(self, name: str) -> str:
        """Get documentation URL for a package."""
