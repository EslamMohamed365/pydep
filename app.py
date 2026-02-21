"""
PyDep - Python Dependency Manager TUI
=======================================

A fully keyboard-driven Terminal User Interface for managing Python project
dependencies via **uv** and ``pyproject.toml``.  Themed with the Tokyo Night
color palette and navigable with Vim motions.

Features
--------
* Lazygit-style multi-panel layout: Status, Sources, Packages, and Details.
* Reads dependencies from ``pyproject.toml``, ``requirements*.txt``,
  ``setup.py``, ``setup.cfg``, ``Pipfile``, and the active virtual
  environment.
* Uses ``uv add`` / ``uv remove`` to manage the dependency list.
* Async PyPI validation before any install/update; defaults to the latest
  version when the user leaves the version field blank.
* Vim-style navigation: ``j``/``k``, ``gg``, ``G``, ``/`` search,
  ``d`` delete, ``Tab`` panel cycling, ``1``/``2``/``3`` panel jump.
* Tokyo Night themed via Textual CSS.

Usage::

    python app.py
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import ast
import configparser

import requests
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    LoadingIndicator,
    Static,
)

# stdlib tomllib (3.11+) with backport fallback.
try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class DepSource:
    """One place where a dependency was declared or found."""

    file: str  # e.g. "pyproject.toml", "requirements-dev.txt", "venv"
    specifier: str  # e.g. ">=2.31", "==8.1.7", "*"


@dataclass
class Package:
    """A dependency aggregated across all discovered sources."""

    name: str
    sources: list[DepSource]  # every file/env that mentions this package
    installed_version: str  # from uv.lock or venv (resolved version)


# =============================================================================
# Package Manager  (uv project-level commands)
# =============================================================================


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

    # -- internal -------------------------------------------------------------

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

    # -- public API -----------------------------------------------------------

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
        """Add or update a dependency.

        ``uv add`` writes to ``pyproject.toml``, updates ``uv.lock``, and
        syncs the virtual environment in one step.  When *group* is given
        (and is not ``"main"``), the ``--group`` flag is forwarded to ``uv``.
        """
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


# =============================================================================
# Dependency Parsing  (multi-source scanner)
# =============================================================================

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


# -- uv.lock parser (unchanged) ----------------------------------------------


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


# -- Sub-parsers --------------------------------------------------------------
# Each returns list[tuple[str, str, str]] = [(raw_name, specifier, source_label)]


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


async def _parse_installed(uv_path: str | None) -> list[tuple[str, str, str]]:
    """Get packages installed in the active venv via ``uv pip list``.

    Returns ``[(name, "==version", "venv"), ...]``.
    """
    if uv_path is None:
        return []
    try:
        proc = await asyncio.create_subprocess_exec(
            uv_path,
            "pip",
            "list",
            "--format",
            "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return []
        packages = json.loads(stdout.decode())
    except Exception:
        return []
    results: list[tuple[str, str, str]] = []
    for pkg in packages:
        name = pkg.get("name", "")
        version = pkg.get("version", "")
        if name and version:
            results.append((name, f"=={version}", "venv"))
    return results


# -- Aggregation --------------------------------------------------------------


def load_dependencies(
    installed: list[tuple[str, str, str]] | None = None,
) -> list[Package]:
    """Scan all dependency sources in CWD and merge by normalised name.

    *installed* is an optional pre-fetched list from ``_parse_installed``
    (since that requires async).  Pass ``None`` to skip venv scanning.

    Returns a sorted list of :class:`Package` objects.
    """
    cwd = Path.cwd()
    raw: list[tuple[str, str, str]] = []

    # 1. pyproject.toml
    raw.extend(_parse_pyproject(cwd / "pyproject.toml"))

    # 2. requirements*.txt  (glob)
    for req_path in sorted(cwd.glob("requirements*.txt")):
        raw.extend(_parse_requirements(req_path))

    # 3. setup.py
    raw.extend(_parse_setup_py(cwd / "setup.py"))

    # 4. setup.cfg
    raw.extend(_parse_setup_cfg(cwd / "setup.cfg"))

    # 5. Pipfile
    raw.extend(_parse_pipfile(cwd / "Pipfile"))

    # 6. Installed (pre-fetched, async)
    if installed:
        raw.extend(installed)

    # Merge by normalised name
    lock_map = _parse_lock(cwd / "uv.lock")
    merged: dict[str, Package] = {}

    for name, spec, source_label in raw:
        key = _normalise(name)
        if key not in merged:
            merged[key] = Package(
                name=name,
                sources=[],
                installed_version=lock_map.get(key, ""),
            )
        pkg = merged[key]
        # Avoid duplicate source entries (same file + same specifier)
        dup = any(s.file == source_label and s.specifier == spec for s in pkg.sources)
        if not dup:
            pkg.sources.append(DepSource(file=source_label, specifier=spec))
        # If this source is "venv" and we don't have an installed version yet,
        # extract it from the ==version specifier.
        if (
            source_label == "venv"
            and not pkg.installed_version
            and spec.startswith("==")
        ):
            pkg.installed_version = spec[2:]

    return sorted(merged.values(), key=lambda p: p.name.lower())


# =============================================================================
# Per-source Removal Helpers
# =============================================================================


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


# =============================================================================
# PyPI Validation
# =============================================================================


async def _get_pypi_json(name: str) -> dict[str, Any] | None:
    """Fetch ``/pypi/<name>/json`` from PyPI. Returns parsed JSON or ``None``."""
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        resp = await asyncio.to_thread(requests.get, url, timeout=(3.05, 10))
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.RequestException:
        return None


async def validate_pypi(
    name: str, version: str | None = None
) -> tuple[bool, str | None, str | None]:
    """Check whether *name* (and optional *version*) exists on PyPI."""
    data = await _get_pypi_json(name)
    if data is None:
        return False, f"Package '{name}' not found on PyPI", None
    info = data.get("info", {})
    latest = info.get("version")
    if version:
        releases = data.get("releases", {})
        if version not in releases:
            return False, f"Version {version} not found for '{name}'", latest
    return True, None, latest


async def _fetch_latest_versions(
    packages: list[str],
) -> dict[str, str | None]:
    """Fetch latest PyPI versions for *packages* concurrently."""
    sem = asyncio.Semaphore(10)

    async def _fetch_one(name: str) -> tuple[str, str | None]:
        async with sem:
            data = await _get_pypi_json(name)
            if data is None:
                return name, None
            return name, data.get("info", {}).get("version")

    results = await asyncio.gather(*[_fetch_one(p) for p in packages])
    return dict(results)


async def _fetch_pypi_index() -> list[str]:
    """Fetch and cache the PyPI package name list from the Simple API."""
    import time as _time

    cache_dir = Path.home() / ".cache" / "pydep"
    cache_file = cache_dir / "pypi_index.json"

    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            if _time.time() - data.get("ts", 0) < 86400:
                return data.get("names", [])
        except Exception:
            pass

    url = "https://pypi.org/simple/"
    headers = {"Accept": "application/vnd.pypi.simple.v1+json"}
    resp = await asyncio.to_thread(requests.get, url, headers=headers, timeout=(5, 30))
    resp.raise_for_status()
    projects = resp.json().get("projects", [])
    names = [p["name"] for p in projects]

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"ts": _time.time(), "names": names}))

    return names


async def _search_pypi_index(query: str, limit: int = 20) -> list[tuple[str, str, str]]:
    """Search PyPI index for packages matching query."""
    names = await _fetch_pypi_index()
    q = query.lower()

    def _score(name: str) -> int:
        n = name.lower()
        if n == q:
            return 0
        if n.startswith(q):
            return 1
        if q in n:
            return 2
        return 99

    matches = [n for n in names if q in n.lower()]
    matches.sort(key=_score)
    top = matches[:limit]

    if not top:
        return []

    sem = asyncio.Semaphore(5)

    async def _fetch_one(name: str) -> tuple[str, str, str]:
        async with sem:
            try:
                url = f"https://pypi.org/pypi/{name}/json"
                resp = await asyncio.to_thread(requests.get, url, timeout=(3.05, 8))
                if resp.status_code == 200:
                    info = resp.json().get("info", {})
                    return (
                        info.get("name", name),
                        info.get("version", ""),
                        info.get("summary", "")[:80],
                    )
            except Exception:
                pass
            return (name, "", "")

    results = await asyncio.gather(*[_fetch_one(n) for n in top])
    return list(results)


# =============================================================================
# Environment Info Helpers
# =============================================================================


def _get_python_version() -> str:
    """Return the Python version string."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _get_app_version() -> str:
    """Read version from ``pyproject.toml``."""
    if tomllib is None:
        return "0.0.0"
    try:
        pyproject = Path(__file__).parent / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text())
            return data.get("project", {}).get("version", "0.0.0")
    except Exception:
        pass
    return "0.0.0"


async def _get_uv_version() -> str:
    """Return the installed uv version string."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "uv",
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            text = stdout.decode().strip()
            parts = text.split()
            return parts[1] if len(parts) >= 2 else text
    except Exception:
        pass
    return "unknown"


async def _get_package_requires(name: str) -> list[str]:
    """Get direct dependencies of a package via ``uv pip show``."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "uv",
            "pip",
            "show",
            name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            for line in stdout.decode().splitlines():
                if line.startswith("Requires:"):
                    reqs = line.split(":", 1)[1].strip()
                    if reqs:
                        return [r.strip() for r in reqs.split(",")]
    except Exception:
        pass
    return []


def _venv_exists() -> bool:
    """Check if a .venv directory exists in CWD."""
    return Path(".venv").is_dir()


# =============================================================================
# Panel Widgets
# =============================================================================


class PanelWidget(Static):
    """Base panel widget with a title and active/inactive border colors.

    Subclass this to create the Status, Sources, Packages, and Details panels.
    The active panel gets a bright border (#7aa2f7), inactive gets dim (#3b4261).
    """

    panel_title: reactive[str] = reactive("")
    is_active: reactive[bool] = reactive(False)

    def __init__(
        self,
        title: str = "",
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.panel_title = title
        self.can_focus = True

    def on_focus(self) -> None:
        self.is_active = True

    def on_blur(self) -> None:
        self.is_active = False

    def watch_is_active(self, active: bool) -> None:
        if active:
            self.add_class("panel-active")
            self.remove_class("panel-inactive")
            self.border_subtitle = "[b #7aa2f7]● focused[/]"
        else:
            self.remove_class("panel-active")
            self.add_class("panel-inactive")
            self.border_subtitle = ""

    def watch_panel_title(self, title: str) -> None:
        self.border_title = title


class StatusPanel(PanelWidget):
    """Non-navigable panel showing project status info."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(title="Status", id="status-panel", **kwargs)
        self._info_text = ""

    def on_mount(self) -> None:
        self.border_title = "Status"
        self.add_class("panel-inactive")

    def update_info(
        self,
        *,
        pkg_count: int = 0,
        source_count: int = 0,
        outdated_count: int = 0,
        uv_version: str = "unknown",
    ) -> None:
        """Rebuild the status display."""
        python_ver = _get_python_version()
        uv_ver = uv_version
        venv_ok = _venv_exists()

        app_version = _get_app_version()
        divider = "[#3b4261]──────────────────────[/]"
        venv_icon = "[#9ece6a]✓[/]" if venv_ok else "[#f7768e]✗[/]"
        venv_label = "[#9ece6a].venv[/]" if venv_ok else "[#f7768e]No venv[/]"

        pkg_line = f"[#565f89]Packages:[/] [#7aa2f7]{pkg_count}[/]"
        if outdated_count:
            pkg_line += f"  │  [#565f89]outdated:[/] [#7aa2f7]{outdated_count}[/]"

        lines: list[str] = [
            f"[bold #7aa2f7]PyDep[/] [#565f89]v{app_version}[/]",
            divider,
            f"[#565f89]Python[/] [#c0caf5]{python_ver}[/]  │  [#565f89]uv[/] [#c0caf5]{uv_ver}[/]",
            f"[#565f89]venv:[/]  {venv_icon} {venv_label}",
            divider,
            pkg_line,
            f"[#565f89]Sources:[/]  [#7aa2f7]{source_count}[/]",
        ]

        self._info_text = "\n".join(lines)
        self.update(self._info_text)


class SourcesPanel(PanelWidget):
    """Navigable list of discovered source files."""

    selected_index: reactive[int] = reactive(0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(title="Sources", id="sources-panel", **kwargs)
        self._sources: list[str] = []

    def on_mount(self) -> None:
        self.border_title = "Sources [0]"
        self.add_class("panel-inactive")

    def set_sources(self, sources: list[str]) -> None:
        """Update the list of source files."""
        self._sources = ["All Sources"] + sources
        if self.selected_index >= len(self._sources):
            self.selected_index = 0
        self.border_title = f"Sources [{len(sources)}]"
        self._render_list()

    def get_selected_source(self) -> str | None:
        """Return the currently selected source, or None for 'All Sources'."""
        if not self._sources or self.selected_index == 0:
            return None
        return self._sources[self.selected_index]

    def _render_list(self) -> None:
        lines: list[str] = []
        if not self._sources:
            lines.append("[#565f89] No sources detected[/]")
            lines.append(
                "[#565f89] [#9ece6a]r[/] refresh  [#9ece6a]i[/] init project[/]"
            )
            self.update("\n".join(lines))
            return

        for i, src in enumerate(self._sources):
            marker = "\u25b8" if i == self.selected_index else " "
            color = "#7aa2f7" if i == 0 else _source_color(src)
            if i == self.selected_index:
                lines.append(f"[b {color}]{marker} {src}[/]")
            else:
                lines.append(f"[#565f89]{marker}[/] [{color}]{src}[/]")
        self.update("\n".join(lines))

    def move_up(self) -> None:
        if self._sources and self.selected_index > 0:
            self.selected_index -= 1
            self._render_list()
            self._scroll_to_selected()

    def move_down(self) -> None:
        if self._sources and self.selected_index < len(self._sources) - 1:
            self.selected_index += 1
            self._render_list()
            self._scroll_to_selected()

    def jump_top(self) -> None:
        if self._sources:
            self.selected_index = 0
            self._render_list()
            self._scroll_to_selected()

    def jump_bottom(self) -> None:
        if self._sources:
            self.selected_index = len(self._sources) - 1
            self._render_list()
            self._scroll_to_selected()

    def _scroll_to_selected(self) -> None:
        """Scroll so the selected item stays visible with context."""
        self.scroll_to(0, max(0, self.selected_index - 2), animate=False)


class PackagesPanel(PanelWidget):
    """Navigable list of packages replacing DataTable."""

    selected_index: reactive[int] = reactive(0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(title="Packages", id="packages-panel", **kwargs)
        self._all_packages: list[Package] = []
        self._filtered_packages: list[Package] = []
        self._latest_versions: dict[str, str] = {}
        self._filter: str = ""
        self._source_filter: str | None = None
        self._filter_active: bool = False

    def on_mount(self) -> None:
        self.border_title = "Packages [0]"
        self.add_class("panel-inactive")

    def set_packages(
        self,
        packages: list[Package],
        latest: dict[str, str] | None = None,
        source_filter: str | None = None,
    ) -> None:
        """Update the package list."""
        self._all_packages = packages
        if latest is not None:
            self._latest_versions = latest
        self._source_filter = source_filter
        self._apply_filters()

    def set_latest_versions(self, latest: dict[str, str]) -> None:
        self._latest_versions = latest
        self._apply_filters()

    def set_source_filter(self, source: str | None) -> None:
        self._source_filter = source
        self._apply_filters()

    def set_text_filter(self, text: str) -> None:
        self._filter = text
        self._apply_filters()

    @property
    def filter_active(self) -> bool:
        return self._filter_active

    @filter_active.setter
    def filter_active(self, val: bool) -> None:
        self._filter_active = val

    def _apply_filters(self) -> None:
        pkgs = self._all_packages

        # Filter by source
        if self._source_filter:
            pkgs = [
                p for p in pkgs if any(s.file == self._source_filter for s in p.sources)
            ]

        # Filter by text
        query = self._filter.lower()
        if query:
            pkgs = [
                p
                for p in pkgs
                if query in p.name.lower()
                or any(query in s.file.lower() for s in p.sources)
            ]

        self._filtered_packages = pkgs
        if self.selected_index >= len(self._filtered_packages):
            self.selected_index = max(0, len(self._filtered_packages) - 1)
        count = len(self._filtered_packages)
        if self._filter:
            self.border_title = f"Packages [{count}] [filter: {self._filter}]"
        else:
            self.border_title = f"Packages [{count}]"
        if self._filter:
            self.add_class("filter-active")
        else:
            self.remove_class("filter-active")
        self._render_list()

    def _render_list(self) -> None:
        lines: list[str] = []
        for i, pkg in enumerate(self._filtered_packages):
            marker = "\u25b8" if i == self.selected_index else " "
            norm = _normalise(pkg.name)
            latest = self._latest_versions.get(norm, "")
            ver = pkg.installed_version or "-"

            if pkg.installed_version and latest:
                if pkg.installed_version == latest:
                    ver_style = "#9ece6a"
                    icon = "●"
                    icon_color = "#9ece6a"
                else:
                    ver_style = "#e0af68"
                    icon = "●"
                    icon_color = "#e0af68"
            elif pkg.installed_version:
                ver_style = "#9ece6a"
                icon = "●"
                icon_color = "#9ece6a"
            else:
                ver_style = "#565f89"
                icon = "○"
                icon_color = "#565f89"

            src_tags = " ".join(_source_abbrev(s.file) for s in pkg.sources)

            if i == self.selected_index:
                lines.append(
                    f"[#c0caf5]{marker} {pkg.name:<20}[/]"
                    f" [{icon_color}]{icon}[/]"
                    f" [{ver_style}]{ver:<10}[/]"
                    f" [#565f89]{src_tags}[/]"
                )
            else:
                lines.append(
                    f"[#565f89]{marker}[/] [#8893b3]{pkg.name:<20}[/]"
                    f" [{icon_color}]{icon}[/]"
                    f" [{ver_style}]{ver:<10}[/]"
                    f" [#3b4261]{src_tags}[/]"
                )

        if not lines:
            lines.append("[#565f89] No packages found[/]")
            lines.append("[#3b4261] ───────────────────────[/]")
            lines.append(
                "[#565f89] [#9ece6a]a[/] add  [#9ece6a]p[/] search PyPI  [#9ece6a]i[/] init  [#9ece6a]r[/] refresh[/]"
            )

        self.update("\n".join(lines))

    def get_selected_package(self) -> Package | None:
        if not self._filtered_packages:
            return None
        if 0 <= self.selected_index < len(self._filtered_packages):
            return self._filtered_packages[self.selected_index]
        return None

    @property
    def package_count(self) -> int:
        return len(self._filtered_packages)

    def move_up(self) -> None:
        if self._filtered_packages and self.selected_index > 0:
            self.selected_index -= 1
            self._render_list()
            self._scroll_to_selected()

    def move_down(self) -> None:
        if (
            self._filtered_packages
            and self.selected_index < len(self._filtered_packages) - 1
        ):
            self.selected_index += 1
            self._render_list()
            self._scroll_to_selected()

    def jump_top(self) -> None:
        if self._filtered_packages:
            self.selected_index = 0
            self._render_list()
            self._scroll_to_selected()

    def jump_bottom(self) -> None:
        if self._filtered_packages:
            self.selected_index = len(self._filtered_packages) - 1
            self._render_list()
            self._scroll_to_selected()

    def _scroll_to_selected(self) -> None:
        """Scroll so the selected item stays visible with context."""
        self.scroll_to(0, max(0, self.selected_index - 2), animate=False)


class DetailsPanel(PanelWidget):
    """Right panel showing details of the selected package."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(title="Details", id="details-panel", **kwargs)
        self.can_focus = False

    def on_mount(self) -> None:
        self.border_title = "Details"
        self.add_class("panel-inactive")
        self.update("[#565f89]Select a package to view details[/]")

    def show_package(
        self,
        pkg: Package | None,
        latest_versions: dict[str, str] | None = None,
        requires: list[str] | None = None,
        summary: str | None = None,
        license_str: str | None = None,
        homepage: str | None = None,
        requires_python: str | None = None,
        author: str | None = None,
    ) -> None:
        if pkg is None:
            self.update("[#565f89]Select a package to view details[/]")
            return

        latest_versions = latest_versions or {}
        norm = _normalise(pkg.name)
        latest = latest_versions.get(norm, "")

        lines: list[str] = []
        lines.append(f"[bold #c0caf5]{pkg.name}[/]")
        lines.append("")

        # Installed version
        ver = pkg.installed_version or "-"
        if pkg.installed_version and latest:
            if pkg.installed_version == latest:
                ver_color = "#9ece6a"
                status = "[#9ece6a]Up to date[/]"
            else:
                ver_color = "#e0af68"
                status = f"[#e0af68]Outdated[/] [#565f89](latest: {latest})[/]"
        elif pkg.installed_version:
            ver_color = "#9ece6a"
            status = "[#565f89]Not checked[/]"
        else:
            ver_color = "#565f89"
            status = "[#565f89]Not installed[/]"

        lines.append(f"  [#7aa2f7]Installed:[/]  [{ver_color}]{ver}[/]")
        if latest:
            lines.append(f"  [#7aa2f7]Latest:[/]     [#7dcfff]{latest}[/]")
        lines.append(f"  [#7aa2f7]Status:[/]     {status}")
        lines.append("")

        # Sources breakdown
        lines.append("  [#7aa2f7]Sources:[/]")
        for src in pkg.sources:
            color = _source_color(src.file)
            lines.append(f"    [{color}]{src.file}[/]  [#bb9af7]{src.specifier}[/]")

        # Dependencies
        if requires:
            lines.append("")
            lines.append("  [#7aa2f7]Dependencies:[/]")
            for req in sorted(requires):
                lines.append(f"    [#565f89]{req}[/]")

        metadata_items: list[tuple[str, str]] = []
        if license_str:
            metadata_items.append(("License:", license_str))
        if requires_python:
            metadata_items.append(("Requires Py:", requires_python))
        if author:
            metadata_items.append(("Author:", author))
        if homepage:
            display_homepage = (
                homepage if len(homepage) <= 50 else f"{homepage[:47]}..."
            )
            metadata_items.append(("Homepage:", display_homepage))

        if metadata_items:
            lines.append("")
            lines.append("  [b #7aa2f7]Metadata[/]")
            lines.append("  [#3b4261]─────────────────────────────[/]")
            for label, value in metadata_items:
                lines.append(f"  [#565f89]{label:<16}[/] [#c0caf5]{value}[/]")

        # Description from PyPI
        if summary:
            lines.append("")
            lines.append("  [#7aa2f7]Description:[/]")
            lines.append(f"    [#565f89]{summary}[/]")

        self.update("\n".join(lines))


# =============================================================================
# Source color helper (module-level)
# =============================================================================

_SOURCE_COLORS: dict[str, str] = {
    "pyproject.toml": "#bb9af7",  # purple
    "requirements": "#7dcfff",  # cyan  (prefix match)
    "setup.py": "#e0af68",  # yellow
    "setup.cfg": "#e0af68",  # yellow
    "Pipfile": "#9ece6a",  # green
    "venv": "#565f89",  # dim
}


_SOURCE_ABBREV: dict[str, str] = {
    "pyproject.toml": "pyproj",
    "requirements.txt": "reqs",
    "requirements-dev.txt": "reqs-d",
    "setup.py": "setup",
    "setup.cfg": "setcfg",
    "Pipfile": "pipf",
}


def _source_abbrev(filename: str) -> str:
    """Return readable abbreviation for a source filename."""
    if filename in _SOURCE_ABBREV:
        return _SOURCE_ABBREV[filename]
    if filename.startswith("pyproject.toml"):
        return "pyproj"
    if filename.startswith("requirements"):
        return "reqs"
    if filename == "venv":
        return "venv"
    return filename[:6]


def _source_color(label: str) -> str:
    """Return the Tokyo Night color for a given source label."""
    for prefix, color in _SOURCE_COLORS.items():
        if label.startswith(prefix) or label == prefix:
            return color
    return "#c0caf5"


# =============================================================================
# Modal Screens
# =============================================================================


class ConfirmModal(ModalScreen[bool]):
    """Yes / No confirmation dialog (``y`` / ``n`` / ``Escape``)."""

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n,escape", "cancel", "No"),
    ]

    def __init__(self, message: str, title: str = "Confirm") -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self._title, id="confirm-title")
            yield Static(self._message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes  [y]", variant="error", id="confirm-btn-yes")
                yield Button("No   [n]", variant="primary", id="confirm-btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-btn-yes")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


# ---------------------------------------------------------------------------


class PackageModal(ModalScreen[tuple[str, str, str] | None]):
    """Base add / update modal with PyPI validation."""

    _modal_title: ClassVar[str] = "Package"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        package_name: str = "",
        package_version: str = "",
        name_disabled: bool = False,
    ) -> None:
        super().__init__()
        self._pkg_name = package_name
        self._pkg_version = package_version
        self._name_disabled = name_disabled

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            yield Static(self._modal_title, id="modal-title")

            yield Static("Package name", classes="modal-label")
            yield Input(
                value=self._pkg_name,
                placeholder="e.g. requests",
                id="input-name",
                disabled=self._name_disabled,
            )

            yield Static("Version  (blank = latest)", classes="modal-label")
            yield Input(
                value=self._pkg_version,
                placeholder="e.g. 2.31.0",
                id="input-version",
            )

            yield Static("Constraint  (blank = ==)", classes="modal-label")
            yield Input(
                placeholder="==",
                id="constraint-input",
            )

            yield Static("", id="validation-error")

            with Horizontal(id="modal-buttons"):
                yield Button("OK", variant="success", id="modal-btn-ok")
                yield Button("Cancel", variant="error", id="modal-btn-cancel")

    def on_mount(self) -> None:
        target = "#input-version" if self._name_disabled else "#input-name"
        self.query_one(target, Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "modal-btn-cancel":
            self.dismiss(None)
        elif event.button.id == "modal-btn-ok":
            self._submit()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self._submit()

    @work(exclusive=True)
    async def _submit(self) -> None:
        name_input = self.query_one("#input-name", Input)
        version_input = self.query_one("#input-version", Input)
        constraint_input = self.query_one("#constraint-input", Input)
        error_label = self.query_one("#validation-error", Static)

        name = name_input.value.strip()
        version_raw = version_input.value.strip() or None
        constraint = constraint_input.value.strip() or "=="

        if not name:
            error_label.update("Package name cannot be empty.")
            return

        error_label.update("Validating on PyPI...")

        valid, error_msg, resolved = await validate_pypi(name, version_raw)

        if not valid:
            error_label.update(error_msg or "Validation failed.")
            return

        error_label.update("")
        self.dismiss((name, resolved or "", constraint))

    def action_cancel(self) -> None:
        self.dismiss(None)


class AddPackageModal(ModalScreen[tuple[str, str, str, str] | None]):
    """Add-package modal with an extra dependency-group field."""

    _modal_title: ClassVar[str] = "Add Package"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        package_name: str = "",
        package_version: str = "",
        name_disabled: bool = False,
    ) -> None:
        super().__init__()
        self._pkg_name = package_name
        self._pkg_version = package_version
        self._name_disabled = name_disabled

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            yield Static(self._modal_title, id="modal-title")

            yield Static("Package name", classes="modal-label")
            yield Input(
                value=self._pkg_name,
                placeholder="e.g. requests",
                id="input-name",
                disabled=self._name_disabled,
            )

            yield Static("Version  (blank = latest)", classes="modal-label")
            yield Input(
                value=self._pkg_version,
                placeholder="e.g. 2.31.0",
                id="input-version",
            )

            yield Static("Constraint  (blank = ==)", classes="modal-label")
            yield Input(
                placeholder="==",
                id="constraint-input",
            )

            yield Static("Group  (blank = main)", classes="modal-label")
            yield Input(
                placeholder="main",
                id="group-input",
            )

            yield Static("", id="validation-error")

            with Horizontal(id="modal-buttons"):
                yield Button("OK", variant="success", id="modal-btn-ok")
                yield Button("Cancel", variant="error", id="modal-btn-cancel")

    def on_mount(self) -> None:
        target = "#input-version" if self._name_disabled else "#input-name"
        self.query_one(target, Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "modal-btn-cancel":
            self.dismiss(None)
        elif event.button.id == "modal-btn-ok":
            self._submit()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self._submit()

    @work(exclusive=True)
    async def _submit(self) -> None:
        name_input = self.query_one("#input-name", Input)
        version_input = self.query_one("#input-version", Input)
        constraint_input = self.query_one("#constraint-input", Input)
        group_input = self.query_one("#group-input", Input)
        error_label = self.query_one("#validation-error", Static)

        name = name_input.value.strip()
        version_raw = version_input.value.strip() or None
        constraint = constraint_input.value.strip() or "=="
        group = group_input.value.strip() or "main"

        if not name:
            error_label.update("Package name cannot be empty.")
            return

        error_label.update("Validating on PyPI...")

        valid, error_msg, resolved = await validate_pypi(name, version_raw)

        if not valid:
            error_label.update(error_msg or "Validation failed.")
            return

        error_label.update("")
        self.dismiss((name, resolved or "", constraint, group))

    def action_cancel(self) -> None:
        self.dismiss(None)


class UpdatePackageModal(PackageModal):
    _modal_title: ClassVar[str] = "Update Package"


_HELP_TEXT = """\
[b #7aa2f7]NAVIGATION[/]
  [#9ece6a]Tab[/]             Cycle panels (Status → Sources → Packages)
  [#9ece6a]Shift+Tab[/]       Previous panel
  [#9ece6a]1[/] / [#9ece6a]2[/] / [#9ece6a]3[/]       Jump to Status / Sources / Packages
  [#9ece6a]j[/] / [#9ece6a]k[/]           Move down / up
  [#9ece6a]g g[/]             Jump to first item
  [#9ece6a]G[/]               Jump to last item
  [#9ece6a]Enter[/]           Select source / Update package

[b #7aa2f7]PACKAGES[/]  (any panel)
  [#9ece6a]a[/]               Add package
  [#9ece6a]p[/]               Search PyPI
  [#9ece6a]u[/]               Update selected package
  [#9ece6a]d[/]               Delete selected package
  [#9ece6a]/[/]               Filter packages
  [#9ece6a]o[/]               Check outdated packages
  [#9ece6a]U[/]               Update all outdated
  [#9ece6a]s[/]               Sync  (uv sync)
  [#9ece6a]L[/]               Lock  (uv lock)
  [#9ece6a]D[/]               Open package docs

[b #7aa2f7]GLOBAL[/]
  [#9ece6a]v[/]               Create virtual environment
  [#9ece6a]r[/]               Refresh
  [#9ece6a]i[/]               Init project  (uv init)
  [#9ece6a]?[/]               Toggle this help
  [#9ece6a]q[/]               Quit

[b #7aa2f7]FILTER MODE[/]  (search input focused)
  [#9ece6a]Escape[/]          Clear and close filter
  [#9ece6a]Enter[/]           Close filter (keep text)
  Type to filter packages in real time.

[b #7aa2f7]MODALS[/]
  [#9ece6a]Tab[/]             Next field
  [#9ece6a]Enter[/]           Submit
  [#9ece6a]Escape[/]          Cancel
"""


class HelpModal(ModalScreen[None]):
    """Keybinding cheat-sheet overlay."""

    BINDINGS = [
        Binding("escape,question_mark,q", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Static("Keyboard Shortcuts", id="help-title")
            yield Static(_HELP_TEXT, id="help-body", markup=True)

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------


class SourceSelectModal(ModalScreen[str | None]):
    """Pick which source file to remove a package from."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    def __init__(self, pkg_name: str, sources: list[DepSource]) -> None:
        super().__init__()
        self._pkg_name = pkg_name
        self._sources = sources
        self._selected = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="source-select-dialog"):
            yield Static(f"Remove '{self._pkg_name}' from:", id="source-select-title")
            yield Static("", id="source-select-list")
            yield Static(
                "[#565f89]j/k move  \u00b7  Enter select  \u00b7  Esc cancel[/]",
                id="source-select-hint",
            )

    def on_mount(self) -> None:
        self._render_list()

    def _render_list(self) -> None:
        lines: list[str] = []
        for i, src in enumerate(self._sources):
            marker = "\u25b8" if i == self._selected else " "
            if i == self._selected:
                lines.append(
                    f"  [#c0caf5]{marker} {i + 1}. {src.file}[/]"
                    f"  [#565f89]({src.specifier})[/]"
                )
            else:
                lines.append(
                    f"  [#565f89]{marker} {i + 1}. {src.file}  ({src.specifier})[/]"
                )
        self.query_one("#source-select-list", Static).update("\n".join(lines))

    def on_key(self, event: events.Key) -> None:
        key = event.key
        if key == "j" or key == "down":
            event.prevent_default()
            event.stop()
            self._selected = min(self._selected + 1, len(self._sources) - 1)
            self._render_list()
            return
        if key == "k" or key == "up":
            event.prevent_default()
            event.stop()
            self._selected = max(self._selected - 1, 0)
            self._render_list()
            return
        if key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(self._sources):
                event.prevent_default()
                event.stop()
                self.dismiss(self._sources[idx].file)
            return

    def action_confirm(self) -> None:
        self.dismiss(self._sources[self._selected].file)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------


class SearchPyPIModal(ModalScreen[str | None]):
    """Search PyPI for packages and select one to add."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._results: list[tuple[str, str, str]] = []
        self._selected: int = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="search-pypi-container"):
            yield Static("Search PyPI", id="search-pypi-title")
            yield Input(
                placeholder="Search packages...",
                id="search-query",
            )
            yield Static("", id="search-status")
            yield Static("", id="search-results")
            yield Static(
                "[#565f89]Type to search PyPI  ·  Enter search  ·  j/k navigate  ·  Enter select  ·  Esc cancel[/]",
                id="search-pypi-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#search-query", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Trigger search when user presses Enter in the input."""
        if event.input.id == "search-query":
            query = event.input.value.strip()
            if query:
                self._do_search(query)

    @work(exclusive=True, group="pypi-search")
    async def _do_search(self, query: str) -> None:
        """Run PyPI search in background."""
        status = self.query_one("#search-status", Static)
        cache_file = Path.home() / ".cache" / "pydep" / "pypi_index.json"

        if not cache_file.exists():
            status.update("[#e0af68]Building search index (first run, ~15s)...[/]")
        else:
            status.update("[#7aa2f7]Searching...[/]")
        self._results = []
        self._selected = 0
        self._render_results()

        try:
            results = await _search_pypi_index(query)
        except Exception:
            results = []
        self._results = results
        self._selected = 0

        if results:
            status.update(
                f"[#9ece6a]{len(results)} result{'s' if len(results) != 1 else ''}[/]"
            )
        else:
            status.update("[#f7768e]No results found[/]")
        self._render_results()
        if self._results:
            self.query_one("#search-query", Input).blur()

    def _render_results(self) -> None:
        """Render the results list with highlighted selection."""
        if not self._results:
            self.query_one("#search-results", Static).update("")
            return
        lines: list[str] = []
        for i, (name, version, desc) in enumerate(self._results):
            marker = "\u25b8" if i == self._selected else " "
            short_desc = desc[:60] + "..." if len(desc) > 60 else desc
            if i == self._selected:
                lines.append(
                    f"  [#c0caf5]{marker} {name}[/]"
                    f"  [#9ece6a]{version}[/]"
                    f"  [#565f89]{short_desc}[/]"
                )
            else:
                lines.append(f"  [#565f89]{marker} {name}  {version}  {short_desc}[/]")
        self.query_one("#search-results", Static).update("\n".join(lines))

    def on_key(self, event: events.Key) -> None:
        """Handle ``j``/``k`` navigation and Enter selection in results."""
        if not self._results:
            return
        key = event.key
        if key == "j" or key == "down":
            event.prevent_default()
            event.stop()
            self._selected = min(self._selected + 1, len(self._results) - 1)
            self._render_results()
            self.query_one("#search-results", Static).scroll_to(
                0, max(0, self._selected - 3), animate=False
            )
            return
        if key == "k" or key == "up":
            event.prevent_default()
            event.stop()
            self._selected = max(self._selected - 1, 0)
            self._render_results()
            self.query_one("#search-results", Static).scroll_to(
                0, max(0, self._selected - 3), animate=False
            )
            return
        if key == "enter":
            # Only select from results if the input is NOT focused
            focused = self.app.focused
            search_input = self.query_one("#search-query", Input)
            if focused is not search_input:
                event.prevent_default()
                event.stop()
                name = self._results[self._selected][0]
                self.dismiss(name)
                return

    def action_cancel(self) -> None:
        self.dismiss(None)


# =============================================================================
# Main Application
# =============================================================================

# Timeout (seconds) for the ``gg`` key sequence.
_GG_TIMEOUT = 0.5


class DependencyManagerApp(App):
    """PyDep - manage Python dependencies with Vim motions."""

    TITLE = "PyDep"
    SUB_TITLE = "Python Dependency Manager"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("a", "add_package", "Add", priority=True),
        Binding("u", "update_package", "Update", priority=True),
        Binding("d", "delete_package", "Delete", priority=True),
        Binding("o", "check_outdated", "Outdated", priority=True),
        Binding("U", "update_all_outdated", "Update All", priority=True),
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("slash", "focus_search", "/Filter", priority=True),
        Binding("i", "init_project", "Init", priority=True),
        Binding("v", "create_venv", "Venv", priority=True),
        Binding("s", "sync", "Sync", priority=True),
        Binding("L", "lock", "Lock", priority=True),
        Binding("p", "search_pypi", "Search PyPI", priority=True),
        Binding("D", "open_docs", "Docs", priority=True),
        Binding("question_mark", "show_help", "?Help", priority=True),
        Binding("q", "quit", "Quit", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.pkg_mgr = PackageManager()
        self._packages: list[Package] = []
        self._filter: str = ""
        self._latest_versions: dict[str, str] = {}
        self._pypi_cache: dict[str, dict[str, Any]] = {}
        # gg sequence state
        self._pending_g: bool = False
        self._pending_g_time: float = 0.0
        # Panel list for Tab cycling (only navigable panels)
        self._panel_ids: list[str] = [
            "status-panel",
            "sources-panel",
            "packages-panel",
        ]
        self._current_panel_idx: int = 2  # start on packages

    # -- helpers ---------------------------------------------------------------

    def _collect_sources(self) -> list[str]:
        """Return sorted unique source file names from all packages."""
        sources: set[str] = set()
        for pkg in self._packages:
            for src in pkg.sources:
                sources.add(src.file)
        return sorted(sources)

    def _count_outdated(self) -> int:
        """Return the number of packages with a known newer version on PyPI."""
        if not self._latest_versions:
            return 0
        return sum(
            1
            for pkg in self._packages
            if pkg.installed_version
            and self._latest_versions.get(_normalise(pkg.name), "")
            and pkg.installed_version
            != self._latest_versions.get(_normalise(pkg.name), "")
        )

    # -- layout ---------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            with Vertical(id="left-column"):
                yield StatusPanel()
                yield SourcesPanel()
                yield PackagesPanel()
            yield DetailsPanel()
        with Horizontal(id="bottom-bar"):
            yield Static("", id="hint-bar")
        with Horizontal(id="filter-bar"):
            yield Input(
                placeholder="Filter packages...",
                id="filter-input",
            )
        with Container(id="loading-overlay"):
            yield LoadingIndicator()
            yield Static("Loading...", id="loading-message")

    async def on_mount(self) -> None:
        # Hide filter bar initially
        self.query_one("#filter-bar").display = False

        # Focus the packages panel
        pkg_panel = self.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        self._current_panel_idx = 2
        self._update_hint_bar()

        toml_path = Path.cwd() / "pyproject.toml"
        if toml_path.is_file():
            self._refresh_data()
        else:
            await self._update_status_panel()
            self.push_screen(
                ConfirmModal(
                    message="No pyproject.toml found.\nInitialise a new uv project?",
                    title="Initialise Project",
                ),
                callback=self._on_init_confirm,
            )

    # -- Vim motion key handler -----------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Intercept keys for Vim navigation and panel management."""
        focused = self.focused
        key = event.key

        # --- filter input: Escape / Enter returns to panels ---
        if isinstance(focused, Input) and focused.id == "filter-input":
            if key == "escape":
                event.prevent_default()
                event.stop()
                # Clear filter and close
                focused.value = ""
                self.query_one("#filter-bar").display = False
                pkg_panel = self.query_one("#packages-panel", PackagesPanel)
                pkg_panel.set_text_filter("")
                pkg_panel.filter_active = False
                pkg_panel.focus()
                self._current_panel_idx = 2
                self._update_details_for_selection()
                self._update_hint_bar()
                return
            if key == "enter":
                event.prevent_default()
                event.stop()
                # Keep filter text, close bar
                self.query_one("#filter-bar").display = False
                pkg_panel = self.query_one("#packages-panel", PackagesPanel)
                pkg_panel.filter_active = False
                pkg_panel.focus()
                self._current_panel_idx = 2
                self._update_details_for_selection()
                self._update_hint_bar()
                return
            return

        # --- Tab: cycle panels ---
        if key == "tab":
            event.prevent_default()
            event.stop()
            self._cycle_panel(1)
            return

        # shift+tab: cycle backwards
        if key == "shift+tab":
            event.prevent_default()
            event.stop()
            self._cycle_panel(-1)
            return

        # --- 1/2/3/4: jump to panel ---
        if key == "1":
            event.prevent_default()
            event.stop()
            self._jump_to_panel(0)
            return
        if key == "2":
            event.prevent_default()
            event.stop()
            self._jump_to_panel(1)
            return
        if key == "3":
            event.prevent_default()
            event.stop()
            self._jump_to_panel(2)
            return
        if key == "4":
            event.prevent_default()
            event.stop()
            self._jump_to_panel(3)
            return

        # --- Panel-specific Vim navigation ---
        panel = self._get_focused_panel()
        if panel is None:
            return

        # j / k movement
        if key == "j":
            event.prevent_default()
            event.stop()
            if isinstance(panel, (SourcesPanel, PackagesPanel)):
                panel.move_down()
                if isinstance(panel, SourcesPanel):
                    self._on_source_selection_changed()
                elif isinstance(panel, PackagesPanel):
                    self._update_details_for_selection()
            return

        if key == "k":
            event.prevent_default()
            event.stop()
            if isinstance(panel, (SourcesPanel, PackagesPanel)):
                panel.move_up()
                if isinstance(panel, SourcesPanel):
                    self._on_source_selection_changed()
                elif isinstance(panel, PackagesPanel):
                    self._update_details_for_selection()
            return

        # G  --  jump to last item
        if key == "G":
            event.prevent_default()
            event.stop()
            if isinstance(panel, (SourcesPanel, PackagesPanel)):
                panel.jump_bottom()
                if isinstance(panel, SourcesPanel):
                    self._on_source_selection_changed()
                elif isinstance(panel, PackagesPanel):
                    self._update_details_for_selection()
            return

        # gg  --  jump to first item (two-key sequence)
        if key == "g":
            event.prevent_default()
            event.stop()
            now = time.monotonic()
            if self._pending_g and (now - self._pending_g_time) < _GG_TIMEOUT:
                self._pending_g = False
                if isinstance(panel, (SourcesPanel, PackagesPanel)):
                    panel.jump_top()
                    if isinstance(panel, SourcesPanel):
                        self._on_source_selection_changed()
                    elif isinstance(panel, PackagesPanel):
                        self._update_details_for_selection()
            else:
                self._pending_g = True
                self._pending_g_time = now
            return

        # Enter on sources panel to select
        if key == "enter" and isinstance(panel, SourcesPanel):
            event.prevent_default()
            event.stop()
            self._on_source_selection_changed()
            return

        # Enter on packages panel opens update modal
        if key == "enter" and isinstance(panel, PackagesPanel):
            event.prevent_default()
            event.stop()
            self.action_update_package()
            return

        # Any other key resets the g-pending state
        if self._pending_g and key != "g":
            self._pending_g = False

    # -- panel focus management -----------------------------------------------

    def _cycle_panel(self, direction: int = 1) -> None:
        self._current_panel_idx = (self._current_panel_idx + direction) % len(
            self._panel_ids
        )
        panel_id = self._panel_ids[self._current_panel_idx]
        self.query_one(f"#{panel_id}").focus()
        self._update_hint_bar()

    def _jump_to_panel(self, idx: int) -> None:
        if 0 <= idx < len(self._panel_ids):
            self._current_panel_idx = idx
            panel_id = self._panel_ids[idx]
            self.query_one(f"#{panel_id}").focus()
            self._update_hint_bar()

    def _get_focused_panel(self) -> PanelWidget | None:
        focused = self.focused
        if isinstance(focused, PanelWidget):
            return focused
        return None

    def _update_hint_bar(self) -> None:
        """Update the bottom hint bar based on the focused panel."""
        hint = self.query_one("#hint-bar", Static)
        focused = self.focused

        if isinstance(focused, StatusPanel):
            hint.update(
                "[#9ece6a]v[/] [#565f89]create venv[/]  "
                "[#9ece6a]i[/] [#565f89]init project[/]  "
                "[#9ece6a]r[/] [#565f89]refresh[/]  "
                "[#9ece6a]?[/] [#565f89]help[/]  "
                "[#9ece6a]q[/] [#565f89]quit[/]"
            )
        elif isinstance(focused, SourcesPanel):
            hint.update(
                "[#9ece6a]j/k[/] [#565f89]navigate[/]  "
                "[#9ece6a]Enter[/] [#565f89]select[/]  "
                "[#9ece6a]?[/] [#565f89]help[/]  "
                "[#9ece6a]q[/] [#565f89]quit[/]"
            )
        elif isinstance(focused, PackagesPanel):
            hint.update(
                "[#9ece6a]j/k[/] [#565f89]navigate[/]  "
                "[#9ece6a]a[/] [#565f89]add[/]  "
                "[#9ece6a]u[/] [#565f89]update[/]  "
                "[#9ece6a]d[/] [#565f89]delete[/]  "
                "[#9ece6a]o[/] [#565f89]outdated[/]  "
                "[#9ece6a]/[/] [#565f89]filter[/]  "
                "[#9ece6a]?[/] [#565f89]help[/]  "
                "[#9ece6a]q[/] [#565f89]quit[/]"
            )
        elif isinstance(focused, Input) and focused.id == "filter-input":
            hint.update(
                "[b #e0af68]Filter Mode[/]  "
                "[#565f89]│[/]  "
                "[#9ece6a]Esc[/] clear & close  "
                "[#565f89]│[/]  "
                "[#9ece6a]Enter[/] keep filter  "
                "[#565f89]│[/]  type to filter in real time"
            )
        elif hasattr(focused, "id") and getattr(focused, "id", None) == "details-panel":
            hint.update(
                "[#9ece6a]D[/] open docs  "
                "[#565f89]│[/]  "
                "[#9ece6a]Tab[/] next panel  "
                "[#565f89]│[/]  "
                "[#9ece6a]?[/] help  "
                "[#565f89]│[/]  "
                "[#9ece6a]q[/] quit"
            )
        else:
            hint.update(
                "[#9ece6a]Tab[/] [#565f89]cycle panels[/]  "
                "[#9ece6a]?[/] [#565f89]help[/]  "
                "[#9ece6a]q[/] [#565f89]quit[/]"
            )

    def on_descendant_focus(self, _event: events.DescendantFocus) -> None:
        self._update_hint_bar()

    def on_descendant_blur(self, _event: events.DescendantBlur) -> None:
        self._update_hint_bar()

    # -- data loading ---------------------------------------------------------

    def _show_loading(self, message: str = "Loading...") -> None:
        """Show the loading overlay with a message."""
        overlay = self.query_one("#loading-overlay", Container)
        overlay.query_one("#loading-message", Static).update(message)
        overlay.display = True

    def _hide_loading(self) -> None:
        """Hide the loading overlay."""
        self.query_one("#loading-overlay", Container).display = False

    @work(exclusive=True, group="refresh")
    async def _refresh_data(self) -> None:
        self._show_loading("Scanning dependency sources...")
        try:
            # Fetch installed packages asynchronously
            installed = await _parse_installed(self.pkg_mgr._uv)
            self._packages = load_dependencies(installed=installed)
        except Exception as exc:
            self.notify(f"Failed to load dependencies: {exc}", severity="error")
            self._packages = []

        # Update all panels
        sources_panel = self.query_one("#sources-panel", SourcesPanel)
        sources_panel.set_sources(self._collect_sources())

        pkg_panel = self.query_one("#packages-panel", PackagesPanel)
        source_filter = sources_panel.get_selected_source()
        pkg_panel.set_packages(
            self._packages,
            latest=self._latest_versions,
            source_filter=source_filter,
        )

        await self._update_status_panel()
        self._update_details_for_selection()
        self._hide_loading()

    async def _update_status_panel(self) -> None:
        """Refresh the status panel counts."""
        uv_ver = await _get_uv_version()
        status = self.query_one("#status-panel", StatusPanel)
        status.update_info(
            pkg_count=len(self._packages),
            source_count=len(self._collect_sources()),
            outdated_count=self._count_outdated(),
            uv_version=uv_ver,
        )

    def _update_details_for_selection(self) -> None:
        """Update the details panel for the currently selected package."""
        pkg_panel = self.query_one("#packages-panel", PackagesPanel)
        details = self.query_one("#details-panel", DetailsPanel)
        pkg = pkg_panel.get_selected_package()
        details.show_package(pkg, self._latest_versions)
        if pkg is not None:
            self._fetch_and_show_requires(pkg)

    @work(exclusive=True, group="requires")
    async def _fetch_and_show_requires(self, pkg: Package) -> None:
        """Fetch dependency list and PyPI summary, then re-render details."""
        requires = await _get_package_requires(pkg.name)
        meta = await self._fetch_pypi_metadata(pkg.name)
        summary: str | None = None
        license_str: str | None = None
        homepage: str | None = None
        requires_python: str | None = None
        author: str | None = None
        if meta:
            info = meta.get("info", {})
            summary = info.get("summary")
            license_str = info.get("license")
            homepage = info.get("home_page")
            requires_python = info.get("requires_python")
            author = info.get("author")
        # Re-check the selection hasn't changed while we were fetching
        pkg_panel = self.query_one("#packages-panel", PackagesPanel)
        current = pkg_panel.get_selected_package()
        if current is not None and _normalise(current.name) == _normalise(pkg.name):
            details = self.query_one("#details-panel", DetailsPanel)
            details.show_package(
                pkg,
                self._latest_versions,
                requires=requires,
                summary=summary,
                license_str=license_str,
                homepage=homepage,
                requires_python=requires_python,
                author=author,
            )

    async def _fetch_pypi_metadata(self, name: str) -> dict[str, Any]:
        """Fetch PyPI JSON metadata with caching."""
        if name in self._pypi_cache:
            return self._pypi_cache[name]
        data = await _get_pypi_json(name)
        if data is not None:
            self._pypi_cache[name] = data
            return data
        return {}

    def _on_source_selection_changed(self) -> None:
        """When the selected source changes, filter the packages panel."""
        sources_panel = self.query_one("#sources-panel", SourcesPanel)
        pkg_panel = self.query_one("#packages-panel", PackagesPanel)
        selected = sources_panel.get_selected_source()
        pkg_panel.set_source_filter(selected)
        self._update_details_for_selection()

    # -- reactive search ------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self._filter = event.value
            pkg_panel = self.query_one("#packages-panel", PackagesPanel)
            pkg_panel.set_text_filter(event.value)
            self._update_details_for_selection()

    # -- actions --------------------------------------------------------------

    def action_focus_search(self) -> None:
        """Show the filter bar and focus it."""
        filter_bar = self.query_one("#filter-bar")
        filter_bar.display = True
        filter_input = self.query_one("#filter-input", Input)
        filter_input.focus()
        pkg_panel = self.query_one("#packages-panel", PackagesPanel)
        pkg_panel.filter_active = True

    def action_refresh(self) -> None:
        self._refresh_data()

    def action_check_outdated(self) -> None:
        self._check_all_outdated()

    @work(exclusive=True, group="outdated")
    async def _check_all_outdated(self) -> None:
        """Query PyPI for the latest version of every loaded package."""
        if not self._packages:
            self.notify("No packages to check.", severity="warning")
            return
        names = [pkg.name for pkg in self._packages]
        self._show_loading(f"Checking {len(names)} packages for updates...")
        try:
            latest_map = await _fetch_latest_versions(names)
        except Exception as exc:
            self._hide_loading()
            self.notify(f"Outdated check failed: {exc}", severity="error")
            return

        failures = sum(1 for version in latest_map.values() if version is None)
        self._latest_versions = {
            _normalise(name): version or "" for name, version in latest_map.items()
        }

        # Update packages panel with latest versions
        pkg_panel = self.query_one("#packages-panel", PackagesPanel)
        pkg_panel.set_latest_versions(self._latest_versions)

        await self._update_status_panel()
        self._update_details_for_selection()
        self._hide_loading()

        # Toast summary
        outdated = self._count_outdated()
        if failures:
            self.notify(
                f"Checked {len(names)} packages. {failures} failed (network errors).",
                severity="warning",
            )
        elif outdated:
            self.notify(
                f"{outdated} package{'s' if outdated != 1 else ''} "
                f"{'have' if outdated != 1 else 'has'} newer versions available.",
                severity="warning",
            )
        else:
            self.notify("All packages are up to date.", severity="information")

    # -- Update all outdated ---------------------------------------------------

    def action_update_all_outdated(self) -> None:
        """Prompt to update every package that has a newer PyPI version."""
        if not self._ensure_toml_or_warn():
            return
        outdated = [
            pkg
            for pkg in self._packages
            if pkg.installed_version
            and self._latest_versions.get(_normalise(pkg.name), "")
            and pkg.installed_version
            != self._latest_versions.get(_normalise(pkg.name), "")
        ]
        if not outdated:
            self.notify("No outdated packages. Press 'o' to check.", severity="warning")
            return
        count = len(outdated)
        self.push_screen(
            ConfirmModal(
                message=f"Update {count} outdated package{'s' if count != 1 else ''} to latest?",
                title="Update All",
            ),
            callback=lambda confirmed: self._on_update_all_confirm(confirmed, outdated),
        )

    def _on_update_all_confirm(
        self, confirmed: bool | None, outdated: list[Package]
    ) -> None:
        if confirmed:
            self._do_update_all(outdated)

    @work(exclusive=True, group="manage")
    async def _do_update_all(self, outdated: list[Package]) -> None:
        """Sequentially update all outdated packages to their latest versions."""
        total = len(outdated)
        failures: list[str] = []
        for i, pkg in enumerate(outdated, 1):
            latest = self._latest_versions.get(_normalise(pkg.name), "")
            self._show_loading(f"Updating {i}/{total}: {pkg.name}...")
            ok, output = await self.pkg_mgr.add(pkg.name, latest)
            if not ok:
                failures.append(pkg.name)
        self._hide_loading()

        succeeded = total - len(failures)
        if failures:
            self.notify(
                f"Updated {succeeded}/{total} packages. Failed: {', '.join(failures)}",
                severity="error",
            )
        else:
            self.notify(
                f"Updated all {total} package{'s' if total != 1 else ''} to latest.",
                severity="information",
            )
        self._refresh_data()

    @work(exclusive=True, group="docs")
    async def action_open_docs(self) -> None:
        """Open documentation URL for the selected package in a browser."""
        pkg = self._selected_package()
        if not pkg:
            self.notify("Select a package first.", severity="warning")
            return
        meta = await self._fetch_pypi_metadata(pkg.name)
        if not meta:
            self.notify("Could not fetch package info", severity="error")
            return
        info = meta.get("info", {})
        urls = info.get("project_urls") or {}
        doc_url = (
            urls.get("Documentation")
            or urls.get("Homepage")
            or info.get("project_url")
            or f"https://pypi.org/project/{pkg.name}/"
        )
        webbrowser.open(doc_url)
        self.notify(f"Opened {doc_url}", severity="information")

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    # -- Init project ---------------------------------------------------------

    def action_init_project(self) -> None:
        toml_path = Path.cwd() / "pyproject.toml"
        if toml_path.is_file():
            self.notify("pyproject.toml already exists.", severity="warning")
            return
        self.push_screen(
            ConfirmModal(
                message="No pyproject.toml found.\nInitialise a new uv project?",
                title="Initialise Project",
            ),
            callback=self._on_init_confirm,
        )

    def _on_init_confirm(self, confirmed: bool | None) -> None:
        if confirmed:
            self._do_init()

    @work(exclusive=True, group="manage")
    async def _do_init(self) -> None:
        self._show_loading("Initialising project...")
        ok, output = await self.pkg_mgr.init_project()
        self._hide_loading()
        if ok:
            self.notify(
                "Project initialised \u2014 pyproject.toml created.",
                severity="information",
            )
        else:
            self.notify(f"Init failed: {output[:200]}", severity="error")
        self._refresh_data()

    # -- Create venv ----------------------------------------------------------

    def action_create_venv(self) -> None:
        if _venv_exists():
            self.notify("Virtual environment already exists.", severity="warning")
            return
        self._do_create_venv()

    @work(exclusive=True, group="manage")
    async def _do_create_venv(self) -> None:
        self._show_loading("Creating virtual environment...")
        ok, output = await self.pkg_mgr.create_venv()
        self._hide_loading()
        if ok:
            self.notify("Created virtual environment (.venv)", severity="information")
        else:
            self.notify(f"Failed to create venv: {output[:200]}", severity="error")
        await self._update_status_panel()

    # -- Sync -----------------------------------------------------------------

    @work(exclusive=True, group="sync")
    async def action_sync(self) -> None:
        """Run ``uv sync`` to install/update all dependencies."""
        self._show_loading("Running uv sync...")
        ok, msg = await self.pkg_mgr.sync()
        self._hide_loading()
        if ok:
            self.notify("Sync complete", severity="information")
            self._refresh_data()
        else:
            self.notify(f"Sync failed: {msg}", severity="error")

    # -- Lock -----------------------------------------------------------------

    @work(exclusive=True, group="lock")
    async def action_lock(self) -> None:
        """Run ``uv lock`` to update the lock file."""
        self._show_loading("Running uv lock...")
        ok, msg = await self.pkg_mgr.lock()
        self._hide_loading()
        if ok:
            self.notify("Lock file updated", severity="information")
        else:
            self.notify(f"Lock failed: {msg}", severity="error")

    # -- Add ------------------------------------------------------------------

    # -- Search PyPI -----------------------------------------------------------

    def action_search_pypi(self) -> None:
        """Open the PyPI search modal."""
        self.push_screen(SearchPyPIModal(), callback=self._on_search_result)

    def _on_search_result(self, result: str | None) -> None:
        """Handle search modal result — confirm before adding."""
        if result is None:
            return
        self.push_screen(
            ConfirmModal(f"Add '{result}' to project?"),
            lambda confirmed: self._on_search_confirm(
                result, confirmed if confirmed is not None else False
            ),
        )

    def _on_search_confirm(self, package: str, confirmed: bool) -> None:
        """Handle search confirmation — open Add modal if confirmed."""
        if not confirmed:
            return
        self.push_screen(
            AddPackageModal(package_name=package),
            self._on_add_result,
        )

    # -- Add ------------------------------------------------------------------

    def action_add_package(self) -> None:
        if not self._ensure_toml_or_warn():
            return
        self.push_screen(AddPackageModal(), callback=self._on_add_result)

    def _on_add_result(self, result: tuple[str, str, str, str] | None) -> None:
        if result is not None:
            self._do_add(result)

    @work(exclusive=True, group="manage")
    async def _do_add(self, result: tuple[str, str, str, str]) -> None:
        name, version, constraint, group = result
        label = f"{name}{constraint}{version}" if version else name
        self._show_loading(f"Adding {label}...")

        ok, output = await self.pkg_mgr.add(
            name, version or None, constraint=constraint, group=group or None
        )
        self._hide_loading()

        if ok:
            target = f" to group '{group}'" if group and group != "main" else ""
            self.notify(
                f"Added {label} to pyproject.toml{target}",
                severity="information",
            )
        else:
            self.notify(f"Failed to add {name}: {output[:200]}", severity="error")
        self._refresh_data()

    # -- Update ---------------------------------------------------------------

    def action_update_package(self) -> None:
        if not self._ensure_toml_or_warn():
            return
        pkg = self._selected_package()
        if pkg is None:
            self.notify("Select a package first.", severity="warning")
            return
        self.push_screen(
            UpdatePackageModal(
                package_name=pkg.name,
                package_version="",
                name_disabled=True,
            ),
            callback=self._on_update_result,
        )

    def _on_update_result(self, result: tuple[str, str, str] | None) -> None:
        if result is not None:
            self._do_update(result)

    @work(exclusive=True, group="manage")
    async def _do_update(self, result: tuple[str, str, str]) -> None:
        name, version, constraint = result
        label = f"{name}{constraint}{version}" if version else name
        self._show_loading(f"Updating {label}...")

        ok, output = await self.pkg_mgr.add(
            name, version or None, constraint=constraint
        )
        self._hide_loading()

        if ok:
            self.notify(f"Updated {label} in pyproject.toml", severity="information")
        else:
            self.notify(f"Failed to update {name}: {output[:200]}", severity="error")
        self._refresh_data()

    # -- Delete ---------------------------------------------------------------

    def action_delete_package(self) -> None:
        if not self._ensure_toml_or_warn():
            return
        pkg = self._selected_package()
        if pkg is None:
            self.notify("Select a package first.", severity="warning")
            return

        if len(pkg.sources) == 1:
            # Single source -> go straight to confirm
            self._confirm_and_remove(pkg, pkg.sources[0].file)
        else:
            # Multiple sources -> let user pick which one
            def _on_source_selected(source_file: str | None) -> None:
                if source_file is not None:
                    self._confirm_and_remove(pkg, source_file)

            self.push_screen(
                SourceSelectModal(pkg.name, pkg.sources),
                callback=_on_source_selected,
            )

    def _confirm_and_remove(self, pkg: Package, source_file: str) -> None:
        """Show a ConfirmModal then route to the correct removal strategy."""

        def _on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._do_remove(pkg, source_file)

        self.push_screen(
            ConfirmModal(
                message=f"Remove '{pkg.name}' from {source_file}?",
                title="Delete Package",
            ),
            callback=_on_confirm,
        )

    @work(exclusive=True, group="manage")
    async def _do_remove(self, pkg: Package, source_file: str) -> None:
        self._show_loading(f"Removing {pkg.name} from {source_file}...")

        # setup.py -> manual only
        if source_file == "setup.py":
            self._hide_loading()
            self.notify(
                "Cannot auto-edit setup.py \u2014 please remove the "
                f"dependency '{pkg.name}' manually.",
                severity="warning",
            )
            return

        ok, output = False, ""
        cwd = Path.cwd()

        if source_file == "pyproject.toml":
            ok, output = await self.pkg_mgr.remove(pkg.name)
        elif source_file.startswith("pyproject.toml ["):
            # Extract group name from "pyproject.toml [groupname]"
            group = source_file.split("[", 1)[1].rstrip("]").strip()
            ok, output = await self.pkg_mgr.remove_from_group(pkg.name, group)
        elif source_file.startswith("requirements"):
            ok, output = _remove_from_requirements(cwd / source_file, pkg.name)
        elif source_file == "setup.cfg":
            ok, output = _remove_from_setup_cfg(cwd / "setup.cfg", pkg.name)
        elif source_file.startswith("Pipfile"):
            ok, output = _remove_from_pipfile(cwd / "Pipfile", pkg.name)
        elif source_file == "venv":
            ok, output = await self.pkg_mgr.pip_uninstall(pkg.name)
        else:
            self._hide_loading()
            self.notify(f"Unknown source: {source_file}", severity="error")
            return

        self._hide_loading()
        if ok:
            self.notify(
                f"Removed {pkg.name} from {source_file}", severity="information"
            )
        else:
            self.notify(
                f"Failed to remove {pkg.name}: {output[:200]}",
                severity="error",
            )
        self._refresh_data()

    # -- helpers --------------------------------------------------------------

    def _selected_package(self) -> Package | None:
        pkg_panel = self.query_one("#packages-panel", PackagesPanel)
        return pkg_panel.get_selected_package()

    def _ensure_toml_or_warn(self) -> bool:
        """Return True if pyproject.toml exists, else notify and return False."""
        if not (Path.cwd() / "pyproject.toml").is_file():
            self.notify(
                "No pyproject.toml found. Press 'i' to init.", severity="warning"
            )
            return False
        return True


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    app = DependencyManagerApp()
    app.run()
