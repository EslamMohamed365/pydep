"""
Headless tests for SetEnv TUI application.

These tests verify:
  1. Module imports (including new DepSource)
  2. PackageManager finds uv
  3. Individual sub-parsers: pyproject.toml, requirements.txt, setup.py,
     setup.cfg, Pipfile
  4. Multi-source merge via load_dependencies()
  5. PyPI validation (4 scenarios)
  6. App lifecycle: mount, table population (5 columns), search filtering
  7. Vim motions: j/k cursor, gg jump to top, G jump to bottom
  8. Modal opening via keybindings: a (Add), u (Update), x (Delete), ? (Help),
     i (Init)
  9. Search mode: / focuses input, Escape/Enter returns to table
 10. Mode indicator updates
 11. Search filters by source name
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# 1. Module imports
# ---------------------------------------------------------------------------


def test_imports():
    """All public symbols should be importable."""
    from app import (
        AddPackageModal,
        ConfirmModal,
        DepSource,
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
    assert DepSource is not None


# ---------------------------------------------------------------------------
# 2. PackageManager
# ---------------------------------------------------------------------------


def test_package_manager_finds_uv():
    """PackageManager should detect ``uv`` on $PATH."""
    from app import PackageManager

    mgr = PackageManager()
    assert mgr._uv is not None


# ---------------------------------------------------------------------------
# 3. Individual sub-parsers
# ---------------------------------------------------------------------------

# -- pyproject.toml -----------------------------------------------------------

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

    [project.optional-dependencies]
    dev = [
        "pytest>=7.0",
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


def test_parse_pyproject(tmp_path: Path):
    """Parse [project].dependencies and optional-dependencies."""
    from app import _parse_pyproject

    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    results = _parse_pyproject(tmp_path / "pyproject.toml")

    names = [r[0] for r in results]
    assert "requests" in names
    assert "httpx" in names
    assert "click" in names
    assert "pytest" in names

    # Check specifiers
    by_name = {r[0]: r for r in results}
    assert by_name["requests"][1] == ">=2.31"
    assert by_name["httpx"][1] == "*"
    assert by_name["click"][1] == "==8.1.7"
    assert by_name["pytest"][1] == ">=7.0"

    # Check source labels
    assert by_name["requests"][2] == "pyproject.toml"
    assert by_name["pytest"][2] == "pyproject.toml [dev]"


def test_parse_pyproject_missing(tmp_path: Path):
    """Returns empty when file doesn't exist."""
    from app import _parse_pyproject

    assert _parse_pyproject(tmp_path / "pyproject.toml") == []


# -- requirements.txt --------------------------------------------------------

_REQUIREMENTS = textwrap.dedent(
    """\
    # Production deps
    requests>=2.31
    httpx==0.28.1
    -r requirements-base.txt
    --index-url https://pypi.org/simple
    click
    """
)


def test_parse_requirements(tmp_path: Path):
    """Parse requirements.txt, skipping comments and flags."""
    from app import _parse_requirements

    req_path = tmp_path / "requirements.txt"
    req_path.write_text(_REQUIREMENTS)
    results = _parse_requirements(req_path)

    names = [r[0] for r in results]
    assert names == ["requests", "httpx", "click"]

    by_name = {r[0]: r for r in results}
    assert by_name["requests"][1] == ">=2.31"
    assert by_name["httpx"][1] == "==0.28.1"
    assert by_name["click"][1] == "*"
    assert by_name["requests"][2] == "requirements.txt"


def test_parse_requirements_dev(tmp_path: Path):
    """requirements-dev.txt is picked up with the correct label."""
    from app import _parse_requirements

    req_path = tmp_path / "requirements-dev.txt"
    req_path.write_text("pytest>=7.0\nruff\n")
    results = _parse_requirements(req_path)

    assert len(results) == 2
    assert results[0][2] == "requirements-dev.txt"


def test_parse_requirements_missing(tmp_path: Path):
    """Returns empty when file doesn't exist."""
    from app import _parse_requirements

    assert _parse_requirements(tmp_path / "requirements.txt") == []


# -- setup.py ----------------------------------------------------------------

_SETUP_PY = textwrap.dedent(
    """\
    from setuptools import setup

    setup(
        name="test-project",
        version="0.1.0",
        install_requires=[
            "requests>=2.31",
            "click==8.1.7",
        ],
    )
    """
)


def test_parse_setup_py(tmp_path: Path):
    """Extract install_requires from setup.py via AST."""
    from app import _parse_setup_py

    (tmp_path / "setup.py").write_text(_SETUP_PY)
    results = _parse_setup_py(tmp_path / "setup.py")

    names = [r[0] for r in results]
    assert "requests" in names
    assert "click" in names

    by_name = {r[0]: r for r in results}
    assert by_name["requests"][1] == ">=2.31"
    assert by_name["click"][1] == "==8.1.7"
    assert by_name["requests"][2] == "setup.py"


def test_parse_setup_py_missing(tmp_path: Path):
    """Returns empty when file doesn't exist."""
    from app import _parse_setup_py

    assert _parse_setup_py(tmp_path / "setup.py") == []


# -- setup.cfg ---------------------------------------------------------------

_SETUP_CFG = textwrap.dedent(
    """\
    [metadata]
    name = test-project

    [options]
    install_requires =
        requests>=2.31
        click==8.1.7
        boto3
    """
)


def test_parse_setup_cfg(tmp_path: Path):
    """Parse [options].install_requires from setup.cfg."""
    from app import _parse_setup_cfg

    (tmp_path / "setup.cfg").write_text(_SETUP_CFG)
    results = _parse_setup_cfg(tmp_path / "setup.cfg")

    names = [r[0] for r in results]
    assert names == ["requests", "click", "boto3"]

    by_name = {r[0]: r for r in results}
    assert by_name["requests"][1] == ">=2.31"
    assert by_name["boto3"][1] == "*"
    assert by_name["requests"][2] == "setup.cfg"


def test_parse_setup_cfg_missing(tmp_path: Path):
    """Returns empty when file doesn't exist."""
    from app import _parse_setup_cfg

    assert _parse_setup_cfg(tmp_path / "setup.cfg") == []


# -- Pipfile ------------------------------------------------------------------

_PIPFILE = textwrap.dedent(
    """\
    [packages]
    requests = ">=2.31"
    httpx = "*"

    [dev-packages]
    pytest = ">=7.0"
    """
)


def test_parse_pipfile(tmp_path: Path):
    """Parse [packages] and [dev-packages] from Pipfile."""
    from app import _parse_pipfile

    (tmp_path / "Pipfile").write_text(_PIPFILE)
    results = _parse_pipfile(tmp_path / "Pipfile")

    names = [r[0] for r in results]
    assert "requests" in names
    assert "httpx" in names
    assert "pytest" in names

    by_name = {r[0]: r for r in results}
    assert by_name["requests"][1] == ">=2.31"
    assert by_name["httpx"][1] == "*"
    assert by_name["pytest"][1] == ">=7.0"
    assert by_name["requests"][2] == "Pipfile"


def test_parse_pipfile_missing(tmp_path: Path):
    """Returns empty when file doesn't exist."""
    from app import _parse_pipfile

    assert _parse_pipfile(tmp_path / "Pipfile") == []


# ---------------------------------------------------------------------------
# 4. Multi-source merge via load_dependencies
# ---------------------------------------------------------------------------


def test_load_dependencies_pyproject_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Parsing pyproject.toml without a lock file."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    monkeypatch.chdir(tmp_path)

    from app import load_dependencies

    deps = load_dependencies()
    assert len(deps) == 4  # requests, httpx, click, pytest (from [dev])
    names = [d.name for d in deps]
    assert "requests" in names
    assert "httpx" in names
    assert "click" in names
    assert "pytest" in names
    # Without a lock file, installed_version should be empty
    for d in deps:
        assert d.installed_version == ""


def test_load_dependencies_with_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Parsing pyproject.toml + uv.lock together."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    from app import load_dependencies

    deps = load_dependencies()
    by_name = {d.name: d for d in deps}

    assert by_name["requests"].installed_version == "2.32.3"
    assert by_name["httpx"].installed_version == "0.28.1"
    assert by_name["click"].installed_version == "8.1.7"

    # Check sources
    req_sources = by_name["requests"].sources
    assert any(
        s.file == "pyproject.toml" and s.specifier == ">=2.31" for s in req_sources
    )


def test_load_dependencies_no_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Returns empty list when no dependency files exist."""
    monkeypatch.chdir(tmp_path)

    from app import load_dependencies

    deps = load_dependencies()
    assert deps == []


def test_load_dependencies_multi_source_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Same package from multiple files merges into one Package with multiple sources."""
    # pyproject.toml has requests>=2.31
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    # requirements.txt also has requests>=2.0
    (tmp_path / "requirements.txt").write_text("requests>=2.0\nflask\n")
    monkeypatch.chdir(tmp_path)

    from app import load_dependencies

    deps = load_dependencies()
    by_name = {d.name: d for d in deps}

    # "requests" should appear once with 2 sources
    assert "requests" in by_name
    req = by_name["requests"]
    source_files = [s.file for s in req.sources]
    assert "pyproject.toml" in source_files
    assert "requirements.txt" in source_files

    # "flask" is only in requirements.txt
    assert "flask" in by_name
    flask = by_name["flask"]
    assert len(flask.sources) == 1
    assert flask.sources[0].file == "requirements.txt"


def test_load_dependencies_with_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Pre-fetched installed packages are merged in."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    monkeypatch.chdir(tmp_path)

    from app import load_dependencies

    installed = [
        ("requests", "==2.32.3", "venv"),
        ("certifi", "==2024.2.2", "venv"),
    ]
    deps = load_dependencies(installed=installed)
    by_name = {d.name: d for d in deps}

    # requests: from pyproject.toml AND venv
    req = by_name["requests"]
    source_files = [s.file for s in req.sources]
    assert "pyproject.toml" in source_files
    assert "venv" in source_files

    # certifi: only from venv, installed_version extracted from ==spec
    cert = by_name["certifi"]
    assert cert.installed_version == "2024.2.2"
    assert len(cert.sources) == 1
    assert cert.sources[0].file == "venv"


# ---------------------------------------------------------------------------
# 5. PyPI validation
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
# 6. App lifecycle tests (headless via Textual pilot)
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

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table", DataTable)
        # pyproject.toml has 3 deps + 1 optional-dep (pytest) = 4
        # uv pip list may add more from the venv -- at minimum we have 4
        assert table.row_count >= 4


@pytest.mark.asyncio
async def test_table_has_five_columns(app_with_deps):
    """Table should have 5 columns: #, Package, Specifier, Installed, Source."""
    from textual.widgets import DataTable

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table", DataTable)
        assert len(table.columns) == 5


@pytest.mark.asyncio
async def test_search_filtering(app_with_deps):
    """Typing in search bar filters table rows."""
    from textual.widgets import DataTable, Input

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
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
async def test_search_by_source(app_with_deps):
    """Search also matches source file names."""
    from textual.widgets import DataTable, Input

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        await pilot.press("slash")
        await pilot.pause()

        search_input = app_with_deps.query_one("#search-input", Input)
        search_input.value = "pyproject"
        await pilot.pause()

        table = app_with_deps.query_one("#dep-table", DataTable)
        # All 4 deps from pyproject.toml should appear
        assert table.row_count >= 3


# ---------------------------------------------------------------------------
# 7. Vim motions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vim_j_k_movement(app_with_deps):
    """j/k keys move the cursor up and down."""
    from textual.widgets import DataTable

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
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

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
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

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
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


# ---------------------------------------------------------------------------
# 8. Search mode focus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_mode_focus(app_with_deps):
    """/ focuses the search bar; Escape returns to the table."""
    from textual.widgets import DataTable, Input

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
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

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
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


# ---------------------------------------------------------------------------
# 9. Mode indicator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mode_indicator_updates(app_with_deps):
    """Mode indicator shows NORMAL when table focused, SEARCH when input focused."""
    from textual.widgets import Static

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
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


# ---------------------------------------------------------------------------
# 10. Modal keybindings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_help_modal_opens(app_with_deps):
    """? opens the help modal."""
    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        table = app_with_deps.query_one("#dep-table")
        table.focus()
        await pilot.pause()

        await pilot.press("question_mark")
        await pilot.pause()

        help_dialog = app_with_deps.screen.query_one("#help-dialog")
        assert help_dialog is not None


@pytest.mark.asyncio
async def test_add_modal_opens(app_with_deps):
    """a opens the Add Package modal."""
    async with app_with_deps.run_test(size=(140, 30)) as pilot:
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
    async with app_with_deps.run_test(size=(140, 30)) as pilot:
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
    async with app_with_deps.run_test(size=(140, 30)) as pilot:
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
    async with app_no_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        # The ConfirmModal should have been pushed automatically
        confirm_dialog = app_no_deps.screen.query_one("#confirm-dialog")
        assert confirm_dialog is not None

        title = app_no_deps.screen.query_one("#confirm-title")
        rendered = str(title.render())
        assert "Initialise" in rendered or "Init" in rendered
