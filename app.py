"""
SetEnv - Python Dependency Manager TUI
=======================================

A fully keyboard-driven Terminal User Interface for managing Python project
dependencies via **uv** and ``pyproject.toml``.  Themed with the Tokyo Night
color palette and navigable with Vim motions.

Features
--------
* Reads ``[project].dependencies`` from ``pyproject.toml`` and resolves locked
  versions from ``uv.lock``.
* Uses ``uv add`` / ``uv remove`` to manage the dependency list (writes back
  to ``pyproject.toml`` automatically).
* Async PyPI validation before any install/update; defaults to the latest
  version when the user leaves the version field blank.
* Vim-style navigation: ``j``/``k``, ``gg``, ``G``, ``/`` search,
  ``x`` delete, and more.
* Tokyo Night themed via Textual CSS.

Usage::

    python app.py
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import httpx
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
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
class Package:
    """A single dependency entry."""

    name: str
    specifier: str  # raw constraint from pyproject.toml  e.g. ">=2.31"
    locked_version: str  # resolved version from uv.lock   e.g. "2.32.5"


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

    async def add(self, package: str, version: str | None = None) -> tuple[bool, str]:
        """Add or update a dependency.

        ``uv add`` writes to ``pyproject.toml``, updates ``uv.lock``, and
        syncs the virtual environment in one step.
        """
        spec = f"{package}=={version}" if version else package
        return await self._run("add", spec)

    async def remove(self, package: str) -> tuple[bool, str]:
        """Remove a dependency from the project."""
        return await self._run("remove", package)


# =============================================================================
# Dependency Parsing  (pyproject.toml + uv.lock)
# =============================================================================

_DEP_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?:\[.*?\])?"  # optional extras
    r"\s*(?P<spec>(?:[><=!~]+\s*[A-Za-z0-9.*+!_-]+\s*,?\s*)*)"
)


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


def _normalise(name: str) -> str:
    """PEP 503 normalisation (lowercase, hyphens/underscores/dots -> -)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def load_dependencies() -> list[Package]:
    """Read ``[project].dependencies`` and cross-reference ``uv.lock``.

    Returns an empty list when no ``pyproject.toml`` is present.
    """
    cwd = Path.cwd()
    toml_path = cwd / "pyproject.toml"

    if not toml_path.is_file() or tomllib is None:
        return []

    try:
        with open(toml_path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return []

    raw_deps: list[str] = data.get("project", {}).get("dependencies", [])
    lock_map = _parse_lock(cwd / "uv.lock")

    packages: list[Package] = []
    for dep in raw_deps:
        m = _DEP_RE.match(dep)
        if not m:
            continue
        name = m.group("name")
        spec = m.group("spec").strip() or "*"
        locked = lock_map.get(_normalise(name), "")
        packages.append(Package(name=name, specifier=spec, locked_version=locked))

    return packages


# =============================================================================
# PyPI Validation
# =============================================================================


async def validate_pypi(
    name: str,
    version: str | None = None,
) -> tuple[bool, str | None, str | None]:
    """Check a package (+ optional version) against the PyPI JSON API.

    Returns ``(is_valid, error_message, resolved_version)``.
    When *version* is ``None`` the latest release is resolved automatically.
    """
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        return False, f"Network error: {exc}", None

    if resp.status_code == 404:
        return False, f"Package '{name}' not found on PyPI.", None
    if resp.status_code != 200:
        return False, f"PyPI returned HTTP {resp.status_code}.", None

    try:
        data = resp.json()
    except Exception:
        return False, "Failed to parse PyPI response.", None

    latest: str = data.get("info", {}).get("version", "")
    releases: dict = data.get("releases", {})

    if version:
        if version in releases:
            return True, None, version
        return (
            False,
            f"Version '{version}' not found for '{name}'. Latest: {latest}",
            latest,
        )

    return True, None, latest


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


class PackageModal(ModalScreen[tuple[str, str] | None]):
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
        error_label = self.query_one("#validation-error", Static)

        name = name_input.value.strip()
        version_raw = version_input.value.strip() or None

        if not name:
            error_label.update("Package name cannot be empty.")
            return

        error_label.update("Validating on PyPI...")

        valid, error_msg, resolved = await validate_pypi(name, version_raw)

        if not valid:
            error_label.update(error_msg or "Validation failed.")
            return

        error_label.update("")
        self.dismiss((name, resolved or ""))

    def action_cancel(self) -> None:
        self.dismiss(None)


class AddPackageModal(PackageModal):
    _modal_title: ClassVar[str] = "Add Package"


class UpdatePackageModal(PackageModal):
    _modal_title: ClassVar[str] = "Update Package"


# ---------------------------------------------------------------------------


_HELP_TEXT = """\
[b #7aa2f7]NORMAL[/]  (table focused)
  [#9ece6a]j[/] / [#9ece6a]k[/]           Move down / up
  [#9ece6a]g g[/]             Jump to first row
  [#9ece6a]G[/]               Jump to last row
  [#9ece6a]/[/]               Enter search mode
  [#9ece6a]a[/]               Add package
  [#9ece6a]u[/]               Update selected package
  [#9ece6a]x[/]               Delete selected package
  [#9ece6a]r[/]               Refresh list
  [#9ece6a]i[/]               Init project  (uv init)
  [#9ece6a]?[/]               Toggle this help
  [#9ece6a]q[/]               Quit

[b #7aa2f7]SEARCH[/]  (search bar focused)
  [#9ece6a]Escape[/]          Return to table
  [#9ece6a]Enter[/]           Return to table
  Type to filter packages in real time.

[b #7aa2f7]MODAL[/]  (inside dialogs)
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


# =============================================================================
# Main Application
# =============================================================================

# Timeout (seconds) for the ``gg`` key sequence.
_GG_TIMEOUT = 0.5


class DependencyManagerApp(App):
    """SetEnv - manage Python dependencies with Vim motions."""

    TITLE = "SetEnv"
    SUB_TITLE = "Python Dependency Manager"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("a", "add_package", "Add", priority=True),
        Binding("u", "update_package", "Update", priority=True),
        Binding("x", "delete_package", "Delete", priority=True),
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("slash", "focus_search", "/Search", priority=True),
        Binding("i", "init_project", "Init", priority=True),
        Binding("question_mark", "show_help", "?Help", priority=True),
        Binding("q", "quit", "Quit", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.pkg_mgr = PackageManager()
        self._packages: list[Package] = []
        self._filter: str = ""
        # gg sequence state
        self._pending_g: bool = False
        self._pending_g_time: float = 0.0

    # -- layout ---------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="search-bar"):
            yield Input(
                placeholder="Filter packages...  (press / to focus)", id="search-input"
            )
        yield DataTable(id="dep-table", zebra_stripes=True, cursor_type="row")
        with Horizontal(id="status-bar"):
            yield Static("NORMAL", id="mode-indicator")
            yield Static("", id="status-info")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#dep-table", DataTable)
        table.add_column("#", width=5, key="idx")
        table.add_column("Package", width=28, key="name")
        table.add_column("Specifier", width=16, key="specifier")
        table.add_column("Locked Version", width=16, key="locked")
        table.focus()

        toml_path = Path.cwd() / "pyproject.toml"
        if toml_path.is_file():
            self._refresh_data()
        else:
            self._set_mode("NORMAL")
            self._set_info("No pyproject.toml found")
            self.push_screen(
                ConfirmModal(
                    message="No pyproject.toml found.\nInitialise a new uv project?",
                    title="Initialise Project",
                ),
                callback=self._on_init_confirm,
            )

    # -- Vim motion key handler -----------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Intercept keys for Vim navigation when the DataTable is focused."""
        focused = self.focused
        table = self.query_one("#dep-table", DataTable)

        # --- search input: Escape / Enter returns to table ---
        if isinstance(focused, Input) and focused.id == "search-input":
            if event.key == "escape":
                event.prevent_default()
                event.stop()
                table.focus()
            return

        # --- only handle vim keys when table is focused ---
        if focused is not table:
            return

        key = event.key

        # j / k  --  cursor movement
        if key == "j":
            event.prevent_default()
            event.stop()
            table.action_cursor_down()
            return
        if key == "k":
            event.prevent_default()
            event.stop()
            table.action_cursor_up()
            return

        # G  --  jump to last row
        if key == "G":
            event.prevent_default()
            event.stop()
            if table.row_count > 0:
                table.move_cursor(row=table.row_count - 1, animate=False)
            return

        # gg  --  jump to first row (two-key sequence)
        if key == "g":
            event.prevent_default()
            event.stop()
            now = time.monotonic()
            if self._pending_g and (now - self._pending_g_time) < _GG_TIMEOUT:
                self._pending_g = False
                if table.row_count > 0:
                    table.move_cursor(row=0, animate=False)
            else:
                self._pending_g = True
                self._pending_g_time = now
            return

        # Any other key resets the g-pending state
        if self._pending_g and key != "g":
            self._pending_g = False

    # -- mode indicator -------------------------------------------------------

    def watch_focused(self) -> None:
        """Called whenever focus changes -- update the mode indicator."""
        focused = self.focused
        if isinstance(focused, DataTable):
            self._set_mode("NORMAL")
        elif isinstance(focused, Input):
            self._set_mode("SEARCH")
        else:
            self._set_mode("NORMAL")

    def on_descendant_focus(self, _event: events.DescendantFocus) -> None:
        self.watch_focused()

    def on_descendant_blur(self, _event: events.DescendantBlur) -> None:
        self.watch_focused()

    # -- data loading ---------------------------------------------------------

    @work(exclusive=True, group="refresh")
    async def _refresh_data(self) -> None:
        self._set_info("Loading...")
        try:
            self._packages = load_dependencies()
        except Exception as exc:
            self.notify(f"Failed to load: {exc}", severity="error")
            self._packages = []
        self._repopulate_table()
        self._set_info(f"{len(self._packages)} deps  |  uv project")

    def _repopulate_table(self) -> None:
        table = self.query_one("#dep-table", DataTable)
        table.clear()
        query = self._filter.lower()
        for idx, pkg in enumerate(self._packages, start=1):
            if query and query not in pkg.name.lower():
                continue
            locked_text = Text(
                pkg.locked_version or "-",
                style="#9ece6a" if pkg.locked_version else "#565f89",
            )
            spec_text = Text(pkg.specifier, style="#bb9af7")
            table.add_row(
                str(idx),
                pkg.name,
                spec_text,
                locked_text,
                key=pkg.name,
            )

    # -- reactive search ------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._filter = event.value
            self._repopulate_table()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Return to the table when Enter is pressed in the search bar."""
        if event.input.id == "search-input":
            self.query_one("#dep-table", DataTable).focus()

    # -- actions --------------------------------------------------------------

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_refresh(self) -> None:
        self._refresh_data()

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
        self._set_info("Initialising project...")
        ok, output = await self.pkg_mgr.init_project()
        if ok:
            self.notify(
                "Project initialised (pyproject.toml created).", severity="information"
            )
        else:
            self.notify(f"Init failed: {output[:200]}", severity="error")
        self._refresh_data()

    # -- Add ------------------------------------------------------------------

    def action_add_package(self) -> None:
        self._ensure_toml_or_warn()
        self.push_screen(AddPackageModal(), callback=self._on_add_result)

    def _on_add_result(self, result: tuple[str, str] | None) -> None:
        if result is not None:
            self._do_add(result)

    @work(exclusive=True, group="manage")
    async def _do_add(self, result: tuple[str, str]) -> None:
        name, version = result
        label = f"{name}=={version}" if version else name
        self.notify(f"Adding {label}...")
        self._set_info(f"uv add {label}...")

        ok, output = await self.pkg_mgr.add(name, version or None)

        if ok:
            self.notify(f"Added {label}", severity="information")
        else:
            self.notify(f"Add failed: {output[:200]}", severity="error")
        self._refresh_data()

    # -- Update ---------------------------------------------------------------

    def action_update_package(self) -> None:
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

    def _on_update_result(self, result: tuple[str, str] | None) -> None:
        if result is not None:
            self._do_update(result)

    @work(exclusive=True, group="manage")
    async def _do_update(self, result: tuple[str, str]) -> None:
        name, version = result
        label = f"{name}=={version}" if version else name
        self.notify(f"Updating {label}...")
        self._set_info(f"uv add {label}...")

        ok, output = await self.pkg_mgr.add(name, version or None)

        if ok:
            self.notify(f"Updated {label}", severity="information")
        else:
            self.notify(f"Update failed: {output[:200]}", severity="error")
        self._refresh_data()

    # -- Delete ---------------------------------------------------------------

    def action_delete_package(self) -> None:
        pkg = self._selected_package()
        if pkg is None:
            self.notify("Select a package first.", severity="warning")
            return

        def _on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._do_remove(pkg)

        self.push_screen(
            ConfirmModal(
                message=f"Remove '{pkg.name}' from project?",
                title="Delete Package",
            ),
            callback=_on_confirm,
        )

    @work(exclusive=True, group="manage")
    async def _do_remove(self, pkg: Package) -> None:
        self.notify(f"Removing {pkg.name}...")
        self._set_info(f"uv remove {pkg.name}...")

        ok, output = await self.pkg_mgr.remove(pkg.name)

        if ok:
            self.notify(f"Removed {pkg.name}", severity="information")
        else:
            self.notify(f"Remove failed: {output[:200]}", severity="error")
        self._refresh_data()

    # -- helpers --------------------------------------------------------------

    def _selected_package(self) -> Package | None:
        table = self.query_one("#dep-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        except Exception:
            return None
        name = row_key.value
        for pkg in self._packages:
            if pkg.name == name:
                return pkg
        return None

    def _ensure_toml_or_warn(self) -> None:
        if not (Path.cwd() / "pyproject.toml").is_file():
            self.notify(
                "No pyproject.toml. Press [i] to initialise.", severity="warning"
            )

    def _set_mode(self, mode: str) -> None:
        indicator = self.query_one("#mode-indicator", Static)
        if mode == "NORMAL":
            indicator.update(Text("-- NORMAL --", style="bold #7aa2f7"))
        elif mode == "SEARCH":
            indicator.update(Text("-- SEARCH --", style="bold #9ece6a"))
        else:
            indicator.update(Text(f"-- {mode} --", style="bold #e0af68"))

    def _set_info(self, text: str) -> None:
        self.query_one("#status-info", Static).update(text)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    app = DependencyManagerApp()
    app.run()
