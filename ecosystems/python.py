from __future__ import annotations

import ast
import asyncio
import configparser
import re
import shutil
from pathlib import Path

from base import DepSource, Ecosystem, Package, RegistryPackageInfo, EnvInfo

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None


_DEP_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?:\[.*?\])?"  # optional extras
    r"\s*(?P<spec>(?:[><=!~]+\s*[A-Za-z0-9.*+!_-]+\s*,?\s*)*)"
)


def _normalise(name: str) -> str:
    """PEP 503 normalisation (lowercase, hyphens/underscores/dots -> -)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_dep_string(raw: str) -> tuple[str, str] | None:
    """Extract ``(name, specifier)`` from a PEP 508 dependency string."""
    m = _DEP_RE.match(raw)
    if not m:
        return None
    name = m.group("name")
    spec = m.group("spec").strip() or "*"
    return name, spec


def _parse_lock(lock_path: Path) -> dict[str, str]:
    """Parse ``uv.lock`` and return a ``{normalised_name: version}`` map.

    ``uv.lock`` is a TOML file with repeated ``[[package]]`` tables.
    """
    if not lock_path.is_file() or tomllib is None:
        return {}
    try:
        with open(lock_path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return {}
    result: dict[str, str] = {}
    for pkg in data.get("package", []):
        name = _normalise(pkg.get("name", ""))
        version = pkg.get("version", "")
        if name and version:
            result[name] = version
    return result


def _parse_pyproject(path: Path) -> list[tuple[str, str, str]]:
    """Parse ``[project].dependencies`` and ``[project].optional-dependencies``."""
    if not path.is_file() or tomllib is None:
        return []
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return []
    results: list[tuple[str, str, str]] = []
    label = path.name  # "pyproject.toml"

    # [project].dependencies
    for raw in data.get("project", {}).get("dependencies", []):
        parsed = _parse_dep_string(raw)
        if parsed:
            results.append((parsed[0], parsed[1], label))

    # [project].optional-dependencies.*
    opt_deps = data.get("project", {}).get("optional-dependencies", {})
    for group_name, deps in opt_deps.items():
        group_label = f"{label} [{group_name}]"
        for raw in deps:
            parsed = _parse_dep_string(raw)
            if parsed:
                results.append((parsed[0], parsed[1], group_label))

    # PEP 735 dependency-groups
    dep_groups = data.get("dependency-groups", {})
    for group_name, group_deps in dep_groups.items():
        group_label = f"{label} [{group_name}]"
        for raw in group_deps:
            if isinstance(raw, str):
                parsed = _parse_dep_string(raw)
                if parsed:
                    results.append((parsed[0], parsed[1], group_label))

    return results


def _parse_requirements(path: Path) -> list[tuple[str, str, str]]:
    """Parse a ``requirements.txt``-style file (line-by-line)."""
    if not path.is_file():
        return []
    results: list[tuple[str, str, str]] = []
    label = path.name
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    for line in lines:
        line = line.strip()
        # skip blank, comments, flags (-r, -e, --index-url, etc.)
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        parsed = _parse_dep_string(line)
        if parsed:
            results.append((parsed[0], parsed[1], label))
    return results


def _parse_setup_py(path: Path) -> list[tuple[str, str, str]]:
    """Extract ``install_requires`` from a ``setup.py`` using AST.

    This is best-effort -- it only handles literal lists, not dynamic code.
    """
    if not path.is_file():
        return []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    results: list[tuple[str, str, str]] = []
    label = "setup.py"

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        # Look for setup(..., install_requires=[...], ...)
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "install_requires":
                continue
            # Try to literal_eval the value
            try:
                deps = ast.literal_eval(kw.value)
            except (ValueError, TypeError):
                continue
            if isinstance(deps, (list, tuple)):
                for raw in deps:
                    if isinstance(raw, str):
                        parsed = _parse_dep_string(raw)
                        if parsed:
                            results.append((parsed[0], parsed[1], label))
    return results


def _parse_setup_cfg(path: Path) -> list[tuple[str, str, str]]:
    """Parse ``[options].install_requires`` from ``setup.cfg``."""
    if not path.is_file():
        return []
    results: list[tuple[str, str, str]] = []
    label = "setup.cfg"
    try:
        cfg = configparser.ConfigParser()
        cfg.read(str(path), encoding="utf-8")
    except Exception:
        return []
    raw = cfg.get("options", "install_requires", fallback="")
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = _parse_dep_string(line)
        if parsed:
            results.append((parsed[0], parsed[1], label))
    return results


def _parse_pipfile(path: Path) -> list[tuple[str, str, str]]:
    """Parse ``[packages]`` and ``[dev-packages]`` from a ``Pipfile``."""
    if not path.is_file() or tomllib is None:
        return []
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return []
    results: list[tuple[str, str, str]] = []
    for section in ("packages", "dev-packages"):
        pkgs = data.get(section, {})
        if not isinstance(pkgs, dict):
            continue
        for name, ver in pkgs.items():
            if isinstance(ver, str):
                spec = ver if ver != "*" else "*"
            elif isinstance(ver, dict):
                spec = ver.get("version", "*")
            else:
                spec = "*"
            results.append((name, spec, "Pipfile"))
    return results


def _remove_from_requirements(path: Path, pkg_name: str) -> tuple[bool, str]:
    """Remove a package line from a ``requirements.txt``-style file."""
    if not path.is_file():
        return False, f"{path.name} not found"
    norm = _normalise(pkg_name)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines: list[str] = []
    removed = False
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
            parsed = _parse_dep_string(stripped)
            if parsed and _normalise(parsed[0]) == norm:
                removed = True
                continue
        new_lines.append(line)
    if not removed:
        return False, f"'{pkg_name}' not found in {path.name}"
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True, f"Removed '{pkg_name}' from {path.name}"


def _remove_from_setup_cfg(path: Path, pkg_name: str) -> tuple[bool, str]:
    """Remove a package from ``setup.cfg`` ``[options].install_requires``."""
    if not path.is_file():
        return False, "setup.cfg not found"
    norm = _normalise(pkg_name)
    cfg = configparser.ConfigParser()
    try:
        cfg.read(str(path), encoding="utf-8")
    except Exception as exc:
        return False, f"Failed to parse setup.cfg: {exc}"
    raw = cfg.get("options", "install_requires", fallback="")
    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    new_lines: list[str] = []
    removed = False
    for line in lines:
        parsed = _parse_dep_string(line)
        if parsed and _normalise(parsed[0]) == norm:
            removed = True
            continue
        new_lines.append(line)
    if not removed:
        return False, f"'{pkg_name}' not found in setup.cfg"
    cfg.set(
        "options",
        "install_requires",
        "\n" + "\n".join(new_lines) if new_lines else "",
    )
    with open(path, "w", encoding="utf-8") as fh:
        cfg.write(fh)
    return True, f"Removed '{pkg_name}' from setup.cfg"


def _remove_from_pipfile(path: Path, pkg_name: str) -> tuple[bool, str]:
    """Remove a package key from ``Pipfile`` (``[packages]`` or ``[dev-packages]``)."""
    if not path.is_file():
        return False, "Pipfile not found"
    norm = _normalise(pkg_name)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    new_lines: list[str] = []
    removed = False
    for line in lines:
        stripped = line.strip()
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*=", stripped)
        if m and _normalise(m.group(1)) == norm:
            removed = True
            continue
        new_lines.append(line)
    if not removed:
        return False, f"'{pkg_name}' not found in Pipfile"
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True, f"Removed '{pkg_name}' from Pipfile"


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
        """Scan for Python dependency sources and merge by normalized name."""
        raw: list[tuple[str, str, str]] = []

        # 1. pyproject.toml
        raw.extend(_parse_pyproject(path / "pyproject.toml"))

        # 2. requirements*.txt  (glob)
        for req_path in sorted(path.glob("requirements*.txt")):
            raw.extend(_parse_requirements(req_path))

        # 3. setup.py
        raw.extend(_parse_setup_py(path / "setup.py"))

        # 4. setup.cfg
        raw.extend(_parse_setup_cfg(path / "setup.cfg"))

        # 5. Pipfile
        raw.extend(_parse_pipfile(path / "Pipfile"))

        # Merge by normalised name
        lock_map = _parse_lock(path / "uv.lock")
        merged: dict[str, Package] = {}

        for name, spec, source_label in raw:
            key = _normalise(name)
            if key not in merged:
                merged[key] = Package(
                    name=name,
                    sources=[],
                    installed_version=lock_map.get(key, ""),
                    ecosystem=self,
                )
            pkg = merged[key]
            # Avoid duplicate source entries
            dup = any(
                s.file == source_label and s.specifier == spec for s in pkg.sources
            )
            if not dup:
                pkg.sources.append(DepSource(file=source_label, specifier=spec))

        return sorted(merged.values(), key=lambda p: p.name.lower())

    async def remove(
        self, package: str, source: str, group: str | None = None
    ) -> tuple[bool, str]:
        """Remove a package from the specified source file."""
        if self._pkg_mgr is None:
            return False, "uv not installed"

        cwd = Path.cwd()

        # Route by source type
        if source == "pyproject.toml":
            if group and group != "main":
                return await self._pkg_mgr.remove_from_group(package, group)
            return await self._pkg_mgr.remove(package)
        elif source.startswith("pyproject.toml ["):
            # Group like "pyproject.toml [dev]"
            group_name = source.split("[")[1].rstrip("]")
            return await self._pkg_mgr.remove_from_group(package, group_name)
        elif source == "requirements.txt" or source.startswith("requirements"):
            return _remove_from_requirements(cwd / source, package)
        elif source == "setup.cfg":
            return _remove_from_setup_cfg(cwd / "setup.cfg", package)
        elif source == "Pipfile":
            return _remove_from_pipfile(cwd / "Pipfile", package)
        elif source == "venv":
            return await self._pkg_mgr.pip_uninstall(package)
        else:
            return False, f"Unknown source: {source}"

    async def init_project(self, path: Path) -> tuple[bool, str]:
        if self._pkg_mgr is None:
            return False, "uv not installed"
        return await self._pkg_mgr.init_project()

    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        if self._pkg_mgr is None:
            return False, "uv not installed"
        return await self._pkg_mgr.add(spec)

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
