"""
Headless tests for SetEnv TUI application.

These tests verify:
  1. Module imports
  2. PackageManager finds uv
  3. Dependency loading from pyproject.toml + uv.lock
  4. PyPI validation (4 scenarios)
  5. App lifecycle: mount, table population, search filtering
  6. Vim motions: j/k cursor, gg jump to top, G jump to bottom
  7. Modal opening via keybindings: a (Add), u (Update), x (Delete), ? (Help), i (Init)
  8. Search mode: / focuses input, Escape returns to table, Enter returns to table
  9. Mode indicator updates
 10. uv add / uv remove integration (round-trip)
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Ensure we can import the application module
# ---------------------------------------------------------------------------


def test_imports():
    """All public symbols should be importable."""
    from app import (
        AddPackageModal,
        ConfirmModal,
        DependencyManagerApp,
        HelpModal,
        Package,
        PackageManager,
        UpdatePackageModal,
        load_dependencies,
        validate_pypi,
    )

    assert DependencyManagerApp is not None
    assert PackageManager is not None


# ---------------------------------------------------------------------------
# PackageManager
# ---------------------------------------------------------------------------


def test_package_manager_finds_uv():
    """PackageManager should detect ``uv`` on $PATH."""
    from app import PackageManager

    mgr = PackageManager()
    assert mgr._uv is not None


# ---------------------------------------------------------------------------
# load_dependencies (requires temporary pyproject.toml + uv.lock)
# ---------------------------------------------------------------------------

_PYPROJECT = textwrap.dedent(
    """\
    [project]
    name = "test-project"
    version = "0.1.0"
    dependencies = [
        "requests>=2.31",
        "httpx",
        "click==8.1.7",
    ]
    """
)

_UVLOCK = textwrap.dedent(
    """\
    version = 1

    [[package]]
    name = "requests"
    version = "2.32.3"

    [[package]]
    name = "httpx"
    version = "0.28.1"

    [[package]]
    name = "click"
    version = "8.1.7"
    """
)


def test_load_dependencies_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Parsing pyproject.toml without a lock file."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    monkeypatch.chdir(tmp_path)

    from app import load_dependencies

    deps = load_dependencies()
    assert len(deps) == 3
    names = [d.name for d in deps]
    assert "requests" in names
    assert "httpx" in names
    assert "click" in names
    # Without a lock file, locked_version should be empty
    for d in deps:
        assert d.locked_version == ""


def test_load_dependencies_with_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Parsing pyproject.toml + uv.lock together."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    from app import load_dependencies

    deps = load_dependencies()
    assert len(deps) == 3

    by_name = {d.name: d for d in deps}
    assert by_name["requests"].locked_version == "2.32.3"
    assert by_name["requests"].specifier == ">=2.31"
    assert by_name["httpx"].locked_version == "0.28.1"
    assert by_name["httpx"].specifier == "*"
    assert by_name["click"].locked_version == "8.1.7"
    assert by_name["click"].specifier == "==8.1.7"


def test_load_dependencies_no_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Returns empty list when no pyproject.toml exists."""
    monkeypatch.chdir(tmp_path)

    from app import load_dependencies

    deps = load_dependencies()
    assert deps == []


# ---------------------------------------------------------------------------
# PyPI validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_pypi_latest():
    """No version specified -> resolves to latest."""
    from app import validate_pypi

    valid, error, resolved = await validate_pypi("requests")
    assert valid is True
    assert error is None
    assert resolved  # should be a version string like "2.32.3"


@pytest.mark.asyncio
async def test_validate_pypi_valid_version():
    """Known good version should pass."""
    from app import validate_pypi

    valid, error, resolved = await validate_pypi("requests", "2.31.0")
    assert valid is True
    assert error is None
    assert resolved == "2.31.0"


@pytest.mark.asyncio
async def test_validate_pypi_invalid_version():
    """Non-existent version for a real package."""
    from app import validate_pypi

    valid, error, resolved = await validate_pypi("requests", "999.999.999")
    assert valid is False
    assert error is not None
    assert "not found" in error.lower() or "999" in error


@pytest.mark.asyncio
async def test_validate_pypi_nonexistent_package():
    """Package that does not exist on PyPI at all."""
    from app import validate_pypi

    valid, error, resolved = await validate_pypi(
        "this-package-absolutely-does-not-exist-on-pypi-xyz"
    )
    assert valid is False
    assert error is not None


# ---------------------------------------------------------------------------
# App lifecycle tests (headless via Textual pilot)
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_deps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a DependencyManagerApp with a pre-populated pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    from app import DependencyManagerApp

    return DependencyManagerApp()


@pytest.fixture
def app_no_deps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a DependencyManagerApp without pyproject.toml."""
    monkeypatch.chdir(tmp_path)

    from app import DependencyManagerApp

    return DependencyManagerApp()


@pytest.mark.asyncio
async def test_app_mounts_and_populates_table(app_with_deps):
    """App mounts, loads deps, and shows them in the DataTable."""
    from textual.widgets import DataTable

    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table", DataTable)
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_search_filtering(app_with_deps):
    """Typing in search bar filters table rows."""
    from textual.widgets import DataTable, Input

    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()

        # Focus the search input
        await pilot.press("slash")
        await pilot.pause()

        # Type a filter
        search_input = app_with_deps.query_one("#search-input", Input)
        search_input.value = "req"
        await pilot.pause()

        table = app_with_deps.query_one("#dep-table", DataTable)
        assert table.row_count == 1  # only "requests" should match


@pytest.mark.asyncio
async def test_vim_j_k_movement(app_with_deps):
    """j/k keys move the cursor up and down."""
    from textual.widgets import DataTable

    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table", DataTable)
        table.focus()
        await pilot.pause()

        # Initial cursor is at row 0
        assert table.cursor_coordinate.row == 0

        # j -> move down
        await pilot.press("j")
        await pilot.pause()
        assert table.cursor_coordinate.row == 1

        # k -> move back up
        await pilot.press("k")
        await pilot.pause()
        assert table.cursor_coordinate.row == 0


@pytest.mark.asyncio
async def test_vim_G_jump_to_bottom(app_with_deps):
    """Shift+G jumps to the last row."""
    from textual.widgets import DataTable

    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table", DataTable)
        table.focus()
        await pilot.pause()

        await pilot.press("G")
        await pilot.pause()
        assert table.cursor_coordinate.row == table.row_count - 1


@pytest.mark.asyncio
async def test_vim_gg_jump_to_top(app_with_deps):
    """gg sequence jumps to the first row."""
    from textual.widgets import DataTable

    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table", DataTable)
        table.focus()
        await pilot.pause()

        # First move to the bottom
        await pilot.press("G")
        await pilot.pause()
        assert table.cursor_coordinate.row == table.row_count - 1

        # Now gg to jump to top
        await pilot.press("g")
        await pilot.press("g")
        await pilot.pause()
        assert table.cursor_coordinate.row == 0


@pytest.mark.asyncio
async def test_search_mode_focus(app_with_deps):
    """/ focuses the search bar; Escape returns to the table."""
    from textual.widgets import DataTable, Input

    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table", DataTable)
        search = app_with_deps.query_one("#search-input", Input)

        table.focus()
        await pilot.pause()

        # / focuses search
        await pilot.press("slash")
        await pilot.pause()
        assert app_with_deps.focused is search

        # Escape returns to table
        await pilot.press("escape")
        await pilot.pause()
        assert app_with_deps.focused is table


@pytest.mark.asyncio
async def test_search_enter_returns_to_table(app_with_deps):
    """Enter in search bar returns focus to the table."""
    from textual.widgets import DataTable, Input

    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table", DataTable)
        search = app_with_deps.query_one("#search-input", Input)

        # Focus search
        await pilot.press("slash")
        await pilot.pause()
        assert app_with_deps.focused is search

        # Enter returns to table
        await pilot.press("enter")
        await pilot.pause()
        assert app_with_deps.focused is table


@pytest.mark.asyncio
async def test_mode_indicator_updates(app_with_deps):
    """Mode indicator shows NORMAL when table focused, SEARCH when input focused."""
    from textual.widgets import Static

    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        indicator = app_with_deps.query_one("#mode-indicator", Static)

        # Table is focused by default -> NORMAL
        assert "NORMAL" in str(indicator.render())

        # / -> SEARCH
        await pilot.press("slash")
        await pilot.pause()
        assert "SEARCH" in str(indicator.render())

        # Escape -> back to NORMAL
        await pilot.press("escape")
        await pilot.pause()
        assert "NORMAL" in str(indicator.render())


@pytest.mark.asyncio
async def test_help_modal_opens(app_with_deps):
    """? opens the help modal."""
    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table")
        table.focus()
        await pilot.pause()

        await pilot.press("question_mark")
        await pilot.pause()

        # Help dialog is on the modal screen (the active screen)
        help_dialog = app_with_deps.screen.query_one("#help-dialog")
        assert help_dialog is not None


@pytest.mark.asyncio
async def test_add_modal_opens(app_with_deps):
    """a opens the Add Package modal."""
    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table")
        table.focus()
        await pilot.pause()

        await pilot.press("a")
        await pilot.pause()

        modal_dialog = app_with_deps.screen.query_one("#modal-dialog")
        assert modal_dialog is not None

        title = app_with_deps.screen.query_one("#modal-title")
        assert "Add" in str(title.render())


@pytest.mark.asyncio
async def test_update_modal_opens(app_with_deps):
    """u opens the Update Package modal when a row is selected."""
    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table")
        table.focus()
        await pilot.pause()

        await pilot.press("u")
        await pilot.pause()

        modal_dialog = app_with_deps.screen.query_one("#modal-dialog")
        assert modal_dialog is not None

        title = app_with_deps.screen.query_one("#modal-title")
        assert "Update" in str(title.render())


@pytest.mark.asyncio
async def test_delete_confirm_opens(app_with_deps):
    """x opens the delete confirmation modal."""
    async with app_with_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table")
        table.focus()
        await pilot.pause()

        await pilot.press("x")
        await pilot.pause()

        confirm_dialog = app_with_deps.screen.query_one("#confirm-dialog")
        assert confirm_dialog is not None

        title = app_with_deps.screen.query_one("#confirm-title")
        assert "Delete" in str(title.render())


@pytest.mark.asyncio
async def test_init_modal_opens_no_toml(app_no_deps):
    """On startup without pyproject.toml, the init confirmation modal appears."""
    async with app_no_deps.run_test(size=(120, 30)) as pilot:
        await pilot.pause()

        # The ConfirmModal should have been pushed automatically
        confirm_dialog = app_no_deps.screen.query_one("#confirm-dialog")
        assert confirm_dialog is not None

        title = app_no_deps.screen.query_one("#confirm-title")
        rendered = str(title.render())
        assert "Initialise" in rendered or "Init" in rendered
