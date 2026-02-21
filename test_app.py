"""
Headless tests for PyDep TUI application (lazygit-style UI).

These tests verify:
  1. Module imports (including new panel widgets)
  2. PackageManager finds uv
  3. Individual sub-parsers: pyproject.toml, requirements.txt, setup.py,
     setup.cfg, Pipfile
  4. Multi-source merge via load_dependencies()
  5. PyPI validation (4 scenarios)
  6. App lifecycle: mount, panel population
  7. Vim motions: j/k cursor in panels, gg jump to top, G jump to bottom
  8. Panel focus: Tab cycles panels, 1/2/3 jumps to panels
  9. Filter mode: / opens filter bar, Escape/Enter closes
 10. Hint bar updates per panel
 11. Package operations: modals for add, update, delete, help
 12. Per-source removal functions
 13. Source-aware deletion flow (single-source vs multi-source)
 14. Outdated check
 15. Details panel updates
 16. Venv creation
 17. Source filtering
"""

from __future__ import annotations

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
        DetailsPanel,
        HelpModal,
        Package,
        PackageManager,
        PackagesPanel,
        PanelWidget,
        SourceSelectModal,
        SearchPyPIModal,
        SourcesPanel,
        StatusPanel,
        UpdatePackageModal,
        _fetch_latest_versions,
        _remove_from_pipfile,
        _remove_from_requirements,
        _remove_from_setup_cfg,
        _source_abbrev,
        load_dependencies,
        validate_pypi,
    )

    assert DependencyManagerApp is not None
    assert PackageManager is not None
    assert DepSource is not None
    assert SourceSelectModal is not None
    assert SearchPyPIModal is not None
    assert _fetch_latest_versions is not None
    assert PanelWidget is not None
    assert StatusPanel is not None
    assert SourcesPanel is not None
    assert PackagesPanel is not None
    assert DetailsPanel is not None


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
async def test_app_mounts_and_populates_packages(app_with_deps):
    """App mounts, loads deps, and shows them in the PackagesPanel."""
    from app import PackagesPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel", PackagesPanel)
        # pyproject.toml has 3 deps + 1 optional-dep (pytest) = 4
        # uv pip list may add more from the venv -- at minimum we have 4
        assert pkg_panel.package_count >= 4


@pytest.mark.asyncio
async def test_app_has_all_panels(app_with_deps):
    """App should have all 4 panel widgets."""
    from app import DetailsPanel, PackagesPanel, SourcesPanel, StatusPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        assert app_with_deps.query_one("#status-panel", StatusPanel) is not None
        assert app_with_deps.query_one("#sources-panel", SourcesPanel) is not None
        assert app_with_deps.query_one("#packages-panel", PackagesPanel) is not None
        assert app_with_deps.query_one("#details-panel", DetailsPanel) is not None


@pytest.mark.asyncio
async def test_status_panel_shows_info(app_with_deps):
    """Status panel should display project info."""
    from app import StatusPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        status = app_with_deps.query_one("#status-panel", StatusPanel)
        rendered = str(status.render())
        assert "PyDep" in rendered
        assert "Python" in rendered


@pytest.mark.asyncio
async def test_sources_panel_populated(app_with_deps):
    """Sources panel should show discovered source files."""
    from app import SourcesPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        sources = app_with_deps.query_one("#sources-panel", SourcesPanel)
        rendered = str(sources.render())
        assert "All Sources" in rendered


@pytest.mark.asyncio
async def test_details_panel_updates_on_selection(app_with_deps):
    """Details panel should show info for the selected package."""
    from app import DetailsPanel, PackagesPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        details = app_with_deps.query_one("#details-panel", DetailsPanel)
        rendered = str(details.render())
        # Should show some package name (first package selected by default)
        # The first alphabetically from our test data
        assert len(rendered) > 10  # has some content


# ---------------------------------------------------------------------------
# 7. Vim motions in panels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vim_j_k_in_packages(app_with_deps):
    """j/k keys move the cursor up and down in PackagesPanel."""
    from app import PackagesPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        await pilot.pause()

        # Initial cursor is at index 0
        assert pkg_panel.selected_index == 0

        # j -> move down
        await pilot.press("j")
        await pilot.pause()
        assert pkg_panel.selected_index == 1

        # k -> move back up
        await pilot.press("k")
        await pilot.pause()
        assert pkg_panel.selected_index == 0


@pytest.mark.asyncio
async def test_vim_G_jump_to_bottom_packages(app_with_deps):
    """Shift+G jumps to the last item in PackagesPanel."""
    from app import PackagesPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        await pilot.pause()

        await pilot.press("G")
        await pilot.pause()
        assert pkg_panel.selected_index == pkg_panel.package_count - 1


@pytest.mark.asyncio
async def test_vim_gg_jump_to_top_packages(app_with_deps):
    """gg sequence jumps to the first item in PackagesPanel."""
    from app import PackagesPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        await pilot.pause()

        # First move to the bottom
        await pilot.press("G")
        await pilot.pause()
        assert pkg_panel.selected_index == pkg_panel.package_count - 1

        # Now gg to jump to top
        await pilot.press("g")
        await pilot.press("g")
        await pilot.pause()
        assert pkg_panel.selected_index == 0


@pytest.mark.asyncio
async def test_vim_j_k_in_sources(app_with_deps):
    """j/k keys navigate in SourcesPanel."""
    from app import SourcesPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        sources = app_with_deps.query_one("#sources-panel", SourcesPanel)
        sources.focus()
        await pilot.pause()

        assert sources.selected_index == 0

        await pilot.press("j")
        await pilot.pause()
        assert sources.selected_index == 1

        await pilot.press("k")
        await pilot.pause()
        assert sources.selected_index == 0


# ---------------------------------------------------------------------------
# 8. Panel focus: Tab cycling and 1/2/3 jump
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tab_cycles_panels(app_with_deps):
    """Tab cycles between Sources and Packages panels (Status excluded from cycle)."""
    from app import PackagesPanel, SourcesPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        await pilot.pause()

        # Packages -> Sources
        await pilot.press("tab")
        await pilot.pause()
        focused = app_with_deps.focused
        assert isinstance(focused, SourcesPanel)

        # Sources -> Packages
        await pilot.press("tab")
        await pilot.pause()
        focused = app_with_deps.focused
        assert isinstance(focused, PackagesPanel)


@pytest.mark.asyncio
async def test_number_keys_jump_panels(app_with_deps):
    """1/2/3 keys jump to specific panels."""
    from app import PackagesPanel, SourcesPanel, StatusPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        # 1 -> Status
        await pilot.press("1")
        await pilot.pause()
        assert isinstance(app_with_deps.focused, StatusPanel)

        # 2 -> Sources
        await pilot.press("2")
        await pilot.pause()
        assert isinstance(app_with_deps.focused, SourcesPanel)

        # 3 -> Packages
        await pilot.press("3")
        await pilot.pause()
        assert isinstance(app_with_deps.focused, PackagesPanel)


# ---------------------------------------------------------------------------
# 9. Filter mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_mode_opens(app_with_deps):
    """/ shows the filter bar and focuses the input."""
    from textual.widgets import Input

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        # Filter bar should be hidden initially
        filter_bar = app_with_deps.query_one("#filter-bar")
        assert filter_bar.display is False

        # / opens filter
        await pilot.press("slash")
        await pilot.pause()
        assert filter_bar.display is True

        filter_input = app_with_deps.query_one("#filter-input", Input)
        assert app_with_deps.focused is filter_input


@pytest.mark.asyncio
async def test_filter_escape_closes(app_with_deps):
    """Escape in filter bar clears and closes it."""
    from app import PackagesPanel
    from textual.widgets import Input

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        await pilot.press("slash")
        await pilot.pause()

        filter_input = app_with_deps.query_one("#filter-input", Input)
        filter_input.value = "req"
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        filter_bar = app_with_deps.query_one("#filter-bar")
        assert filter_bar.display is False
        assert filter_input.value == ""

        # Focus should return to packages
        assert isinstance(app_with_deps.focused, PackagesPanel)


@pytest.mark.asyncio
async def test_filter_enter_keeps_text(app_with_deps):
    """Enter in filter bar closes it but keeps the filter text."""
    from app import PackagesPanel
    from textual.widgets import Input

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        await pilot.press("slash")
        await pilot.pause()

        filter_input = app_with_deps.query_one("#filter-input", Input)
        filter_input.value = "req"
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        filter_bar = app_with_deps.query_one("#filter-bar")
        assert filter_bar.display is False

        # Focus should return to packages
        assert isinstance(app_with_deps.focused, PackagesPanel)


@pytest.mark.asyncio
async def test_filter_filters_packages(app_with_deps):
    """Typing in filter bar filters the packages panel."""
    from app import PackagesPanel
    from textual.widgets import Input

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        pkg_panel = app_with_deps.query_one("#packages-panel", PackagesPanel)
        initial_count = pkg_panel.package_count

        await pilot.press("slash")
        await pilot.pause()

        filter_input = app_with_deps.query_one("#filter-input", Input)
        filter_input.value = "req"
        await pilot.pause()

        # Should filter to fewer packages
        assert pkg_panel.package_count < initial_count
        assert pkg_panel.package_count >= 1  # at least "requests"


# ---------------------------------------------------------------------------
# 10. Hint bar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hint_bar_updates(app_with_deps):
    """Hint bar shows contextual hints per panel."""
    from app import PackagesPanel, SourcesPanel, StatusPanel
    from textual.widgets import Static

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        hint = app_with_deps.query_one("#hint-bar", Static)

        # Packages panel focused
        pkg_panel = app_with_deps.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        await pilot.pause()
        rendered = str(hint.render())
        assert "add" in rendered
        assert "filter" in rendered

        # Status panel
        await pilot.press("1")
        await pilot.pause()
        rendered = str(hint.render())
        assert "venv" in rendered

        # Sources panel
        await pilot.press("2")
        await pilot.pause()
        rendered = str(hint.render())
        assert "navigate" in rendered


# ---------------------------------------------------------------------------
# 11. Modal keybindings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_help_modal_opens(app_with_deps):
    """? opens the help modal."""
    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel")
        pkg_panel.focus()
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
        pkg_panel = app_with_deps.query_one("#packages-panel")
        pkg_panel.focus()
        await pilot.pause()

        await pilot.press("a")
        await pilot.pause()

        modal_dialog = app_with_deps.screen.query_one("#modal-dialog")
        assert modal_dialog is not None

        title = app_with_deps.screen.query_one("#modal-title")
        assert "Add" in str(title.render())


@pytest.mark.asyncio
async def test_add_modal_has_group_selector(app_with_deps):
    """Add modal contains a group-input field; Update modal does not."""
    from app import AddPackageModal, Input, UpdatePackageModal

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel")
        pkg_panel.focus()
        await pilot.pause()

        # Open the Add modal
        await pilot.press("a")
        await pilot.pause()

        assert isinstance(app_with_deps.screen, AddPackageModal)

        # Group input should exist with placeholder "main"
        group_input = app_with_deps.screen.query_one("#group-input", Input)
        assert group_input is not None
        assert group_input.placeholder == "main"

        # Dismiss the Add modal
        await pilot.press("escape")
        await pilot.pause()

        # Open the Update modal
        await pilot.press("u")
        await pilot.pause()

        assert isinstance(app_with_deps.screen, UpdatePackageModal)

        # Update modal should NOT have a group input
        matches = app_with_deps.screen.query("#group-input")
        assert len(matches) == 0


@pytest.mark.asyncio
async def test_add_modal_has_constraint_picker(app_with_deps):
    """Add modal contains a constraint-input field with correct defaults."""
    from app import AddPackageModal, Input

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel")
        pkg_panel.focus()
        await pilot.pause()

        # Open the Add modal
        await pilot.press("a")
        await pilot.pause()

        assert isinstance(app_with_deps.screen, AddPackageModal)

        # Constraint input should exist with placeholder "=="
        constraint_input = app_with_deps.screen.query_one("#constraint-input", Input)
        assert constraint_input is not None
        assert constraint_input.placeholder == "=="


@pytest.mark.asyncio
async def test_update_modal_has_constraint_picker(app_with_deps):
    """Update modal contains a constraint-input field with correct defaults."""
    from app import Input, UpdatePackageModal

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel")
        pkg_panel.focus()
        await pilot.pause()

        # Open the Update modal
        await pilot.press("u")
        await pilot.pause()

        assert isinstance(app_with_deps.screen, UpdatePackageModal)

        # Constraint input should exist with placeholder "=="
        constraint_input = app_with_deps.screen.query_one("#constraint-input", Input)
        assert constraint_input is not None
        assert constraint_input.placeholder == "=="


@pytest.mark.asyncio
async def test_update_modal_opens(app_with_deps):
    """u opens the Update Package modal when a package is selected."""
    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel")
        pkg_panel.focus()
        await pilot.pause()

        await pilot.press("u")
        await pilot.pause()

        modal_dialog = app_with_deps.screen.query_one("#modal-dialog")
        assert modal_dialog is not None

        title = app_with_deps.screen.query_one("#modal-title")
        assert "Update" in str(title.render())


@pytest.mark.asyncio
async def test_delete_confirm_opens(app_with_deps):
    """d opens the delete confirmation modal (single-source package)."""
    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel")
        pkg_panel.focus()
        await pilot.pause()

        await pilot.press("d")
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


@pytest.mark.asyncio
async def test_ensure_toml_blocks_add(app_no_deps):
    """Add action should be blocked when no pyproject.toml exists."""
    from app import AddPackageModal

    async with app_no_deps.run_test() as pilot:
        await pilot.pause()
        # Dismiss the init confirmation modal first
        await pilot.press("n")
        await pilot.pause()
        # Now try to add a package — should be blocked
        await pilot.press("a")
        await pilot.pause()
        # AddPackageModal should NOT be on the screen stack
        assert not isinstance(app_no_deps.screen, AddPackageModal)


# ---------------------------------------------------------------------------
# 12. Per-source removal functions
# ---------------------------------------------------------------------------


def test_remove_from_requirements(tmp_path: Path):
    """Remove a package line from requirements.txt."""
    from app import _remove_from_requirements

    req = tmp_path / "requirements.txt"
    req.write_text("# deps\nrequests>=2.31\nhttpx==0.28.1\nclick\n")

    ok, msg = _remove_from_requirements(req, "httpx")
    assert ok is True
    assert "httpx" in msg

    content = req.read_text()
    assert "httpx" not in content
    assert "requests>=2.31" in content
    assert "click" in content
    assert "# deps" in content  # comments preserved


def test_remove_from_requirements_missing_pkg(tmp_path: Path):
    """Removing a non-existent package returns failure without modifying the file."""
    from app import _remove_from_requirements

    req = tmp_path / "requirements.txt"
    original = "requests>=2.31\nclick\n"
    req.write_text(original)

    ok, msg = _remove_from_requirements(req, "flask")
    assert ok is False
    assert "not found" in msg.lower()

    # File should be unchanged
    assert req.read_text() == original


def test_remove_from_requirements_missing_file(tmp_path: Path):
    """Removing from a non-existent file returns failure."""
    from app import _remove_from_requirements

    ok, msg = _remove_from_requirements(tmp_path / "requirements.txt", "requests")
    assert ok is False
    assert "not found" in msg.lower()


def test_remove_from_setup_cfg(tmp_path: Path):
    """Remove a package from setup.cfg [options].install_requires."""
    from app import _remove_from_setup_cfg

    cfg_path = tmp_path / "setup.cfg"
    cfg_path.write_text(_SETUP_CFG)

    ok, msg = _remove_from_setup_cfg(cfg_path, "click")
    assert ok is True
    assert "click" in msg

    # Re-parse to verify
    import configparser

    cfg = configparser.ConfigParser()
    cfg.read(str(cfg_path))
    raw = cfg.get("options", "install_requires", fallback="")
    remaining = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    names = [l.split(">")[0].split("=")[0].split("<")[0].strip() for l in remaining]
    assert "click" not in names
    assert "requests" in names
    assert "boto3" in names


def test_remove_from_setup_cfg_missing_pkg(tmp_path: Path):
    """Removing a non-existent package from setup.cfg returns failure."""
    from app import _remove_from_setup_cfg

    cfg_path = tmp_path / "setup.cfg"
    cfg_path.write_text(_SETUP_CFG)

    ok, msg = _remove_from_setup_cfg(cfg_path, "flask")
    assert ok is False
    assert "not found" in msg.lower()


def test_remove_from_pipfile(tmp_path: Path):
    """Remove a package from Pipfile [packages]."""
    from app import _remove_from_pipfile

    pf = tmp_path / "Pipfile"
    pf.write_text(_PIPFILE)

    ok, msg = _remove_from_pipfile(pf, "requests")
    assert ok is True
    assert "requests" in msg

    content = pf.read_text()
    assert "requests" not in content
    assert "httpx" in content
    assert "pytest" in content  # dev-packages preserved


def test_remove_from_pipfile_dev(tmp_path: Path):
    """Remove a dev package from Pipfile [dev-packages]."""
    from app import _remove_from_pipfile

    pf = tmp_path / "Pipfile"
    pf.write_text(_PIPFILE)

    ok, msg = _remove_from_pipfile(pf, "pytest")
    assert ok is True

    content = pf.read_text()
    assert "pytest" not in content
    assert "requests" in content  # packages preserved
    assert "httpx" in content


def test_remove_from_pipfile_missing_pkg(tmp_path: Path):
    """Removing a non-existent package from Pipfile returns failure."""
    from app import _remove_from_pipfile

    pf = tmp_path / "Pipfile"
    pf.write_text(_PIPFILE)

    ok, msg = _remove_from_pipfile(pf, "flask")
    assert ok is False
    assert "not found" in msg.lower()


# ---------------------------------------------------------------------------
# 13. Source-aware deletion flow
# ---------------------------------------------------------------------------


@pytest.fixture
def app_multi_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """App with a package appearing in both pyproject.toml and requirements.txt."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    # requirements.txt also has requests, creating a multi-source package
    (tmp_path / "requirements.txt").write_text("requests>=2.0\n")
    monkeypatch.chdir(tmp_path)

    from app import DependencyManagerApp

    return DependencyManagerApp()


@pytest.mark.asyncio
async def test_multi_source_delete_opens_source_select(app_multi_source):
    """d on a multi-source package opens SourceSelectModal instead of ConfirmModal."""
    from app import PackagesPanel

    async with app_multi_source.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_multi_source.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        await pilot.pause()

        # Navigate to "requests" which should have 2+ sources
        for i in range(pkg_panel.package_count):
            pkg = pkg_panel.get_selected_package()
            if pkg and pkg.name == "requests":
                break
            await pilot.press("j")
            await pilot.pause()

        await pilot.press("d")
        await pilot.pause()

        # SourceSelectModal should be showing (not ConfirmModal directly)
        source_dialog = app_multi_source.screen.query_one("#source-select-dialog")
        assert source_dialog is not None


@pytest.mark.asyncio
async def test_source_select_modal_escape_cancels(app_multi_source):
    """Escape in SourceSelectModal dismisses without removal."""
    from app import PackagesPanel

    async with app_multi_source.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_multi_source.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        await pilot.pause()

        # Navigate to "requests"
        for i in range(pkg_panel.package_count):
            pkg = pkg_panel.get_selected_package()
            if pkg and pkg.name == "requests":
                break
            await pilot.press("j")
            await pilot.pause()

        initial_count = pkg_panel.package_count

        await pilot.press("d")
        await pilot.pause()

        # Escape should dismiss the modal
        await pilot.press("escape")
        await pilot.pause()

        # Should be back to the main screen, packages unchanged
        assert pkg_panel.package_count == initial_count


@pytest.mark.asyncio
async def test_source_select_modal_enter_opens_confirm(app_multi_source):
    """Selecting a source in SourceSelectModal proceeds to ConfirmModal."""
    from app import PackagesPanel

    async with app_multi_source.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_multi_source.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        await pilot.pause()

        # Navigate to "requests"
        for i in range(pkg_panel.package_count):
            pkg = pkg_panel.get_selected_package()
            if pkg and pkg.name == "requests":
                break
            await pilot.press("j")
            await pilot.pause()

        await pilot.press("d")
        await pilot.pause()

        # Press Enter to select the first source
        await pilot.press("enter")
        await pilot.pause()

        # Now a ConfirmModal should appear
        confirm_dialog = app_multi_source.screen.query_one("#confirm-dialog")
        assert confirm_dialog is not None

        title = app_multi_source.screen.query_one("#confirm-title")
        assert "Delete" in str(title.render())


@pytest.mark.asyncio
async def test_single_source_delete_skips_source_select(app_with_deps):
    """d on a single-source package goes directly to ConfirmModal."""
    from app import PackagesPanel

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        await pilot.pause()

        await pilot.press("d")
        await pilot.pause()

        # Should be ConfirmModal directly (no SourceSelectModal)
        confirm_dialog = app_with_deps.screen.query_one("#confirm-dialog")
        assert confirm_dialog is not None

        # Verify the message mentions the source file
        message = app_with_deps.screen.query_one("#confirm-message")
        rendered = str(message.render())
        assert "pyproject.toml" in rendered or "Remove" in rendered


# ---------------------------------------------------------------------------
# 14. Outdated check: _fetch_latest_versions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_latest_versions():
    """Batch query should return latest versions for known packages."""
    from app import _fetch_latest_versions

    versions, failures = await _fetch_latest_versions(["requests", "httpx"])
    assert failures == 0
    assert "requests" in versions
    assert "httpx" in versions
    # Versions should be non-empty strings
    assert len(versions["requests"]) > 0
    assert len(versions["httpx"]) > 0


@pytest.mark.asyncio
async def test_fetch_latest_versions_nonexistent():
    """Non-existent packages are counted as failures, not errors."""
    from app import _fetch_latest_versions

    versions, failures = await _fetch_latest_versions(
        ["this-package-does-not-exist-xyz-12345"]
    )
    assert failures == 1
    assert len(versions) == 0


@pytest.mark.asyncio
async def test_fetch_latest_versions_empty():
    """Empty input returns empty results."""
    from app import _fetch_latest_versions

    versions, failures = await _fetch_latest_versions([])
    assert versions == {}
    assert failures == 0


# ---------------------------------------------------------------------------
# 15. Outdated check: UI integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loading_overlay_exists_hidden(app_with_deps):
    """Loading overlay widget exists but is hidden by default."""
    from textual.containers import Container

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        overlay = app_with_deps.query_one("#loading-overlay", Container)
        assert overlay is not None
        assert overlay.display is False


@pytest.mark.asyncio
async def test_outdated_check_with_mock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Pressing 'o' triggers the outdated check and populates latest versions."""
    from app import DependencyManagerApp, _normalise

    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    app = DependencyManagerApp()

    async def mock_fetch(packages):
        return {_normalise(n): "99.0.0" for n in packages}, 0

    monkeypatch.setattr("app._fetch_latest_versions", mock_fetch)

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app.query_one("#packages-panel")
        pkg_panel.focus()
        await pilot.pause()

        await pilot.press("o")
        await pilot.pause()
        await pilot.pause()  # extra pause for async worker

        # After outdated check, _latest_versions should be populated
        assert len(app._latest_versions) > 0

        # All packages should have "99.0.0" as latest
        for key in app._latest_versions:
            assert app._latest_versions[key] == "99.0.0"


@pytest.mark.asyncio
async def test_outdated_status_panel_shows_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """After outdated check, status panel shows outdated count."""
    from app import DependencyManagerApp, StatusPanel, _normalise

    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    app = DependencyManagerApp()

    # Mock: all packages have a newer version available
    async def mock_fetch(packages):
        return {_normalise(n): "99.0.0" for n in packages}, 0

    monkeypatch.setattr("app._fetch_latest_versions", mock_fetch)

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        await pilot.press("o")
        await pilot.pause()
        await pilot.pause()

        status = app.query_one("#status-panel", StatusPanel)
        rendered = str(status.render())
        assert "outdated" in rendered


@pytest.mark.asyncio
async def test_outdated_check_all_up_to_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """When all packages are up to date, status panel has no 'outdated' count."""
    from app import DependencyManagerApp, StatusPanel, _normalise

    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    app = DependencyManagerApp()

    # Mock: versions match what's in uv.lock
    async def mock_fetch(packages):
        lock_versions = {"requests": "2.32.3", "httpx": "0.28.1", "click": "8.1.7"}
        result = {}
        for name in packages:
            key = _normalise(name)
            if key in lock_versions:
                result[key] = lock_versions[key]
        return result, 0

    monkeypatch.setattr("app._fetch_latest_versions", mock_fetch)

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        await pilot.press("o")
        await pilot.pause()
        await pilot.pause()

        status = app.query_one("#status-panel", StatusPanel)
        rendered = str(status.render())
        assert "outdated" not in rendered


@pytest.mark.asyncio
async def test_help_modal_shows_new_keybindings(app_with_deps):
    """Help modal includes the new keybindings (Tab, 1/2/3, v)."""
    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel")
        pkg_panel.focus()
        await pilot.pause()

        await pilot.press("question_mark")
        await pilot.pause()

        from textual.widgets import Static

        help_body = app_with_deps.screen.query_one("#help-body", Static)
        rendered = str(help_body.render())
        assert "Tab" in rendered
        assert "outdated" in rendered.lower()
        assert "venv" in rendered.lower() or "virtual" in rendered.lower()


# ---------------------------------------------------------------------------
# 16. Venv creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_venv_creation_warns_if_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Pressing v when .venv already exists shows a warning."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    (tmp_path / ".venv").mkdir()  # create the venv dir
    monkeypatch.chdir(tmp_path)

    from app import DependencyManagerApp

    app = DependencyManagerApp()

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
        # The app should show a toast warning, no crash


@pytest.mark.asyncio
async def test_status_panel_shows_venv_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Status panel shows venv existence status."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    (tmp_path / ".venv").mkdir()
    monkeypatch.chdir(tmp_path)

    from app import DependencyManagerApp, StatusPanel

    app = DependencyManagerApp()

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        status = app.query_one("#status-panel", StatusPanel)
        rendered = str(status.render())
        # Should show venv exists indicator
        assert ".venv" in rendered


@pytest.mark.asyncio
async def test_status_panel_shows_no_venv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Status panel shows 'No venv' when .venv doesn't exist."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    from app import DependencyManagerApp, StatusPanel

    app = DependencyManagerApp()

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        status = app.query_one("#status-panel", StatusPanel)
        rendered = str(status.render())
        assert "No venv" in rendered


# ---------------------------------------------------------------------------
# 17. Source filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_source_selection_filters_packages(app_multi_source):
    """Selecting a specific source in SourcesPanel filters PackagesPanel."""
    from app import PackagesPanel, SourcesPanel

    async with app_multi_source.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        sources = app_multi_source.query_one("#sources-panel", SourcesPanel)
        pkg_panel = app_multi_source.query_one("#packages-panel", PackagesPanel)

        all_count = pkg_panel.package_count

        # Focus sources and navigate to a specific source
        sources.focus()
        await pilot.pause()

        # Move to first actual source (past "All Sources")
        await pilot.press("j")
        await pilot.pause()

        # Press enter to select
        await pilot.press("enter")
        await pilot.pause()

        # Package count should be <= all_count (filtered)
        filtered_count = pkg_panel.package_count
        assert filtered_count <= all_count


# ---------------------------------------------------------------------------
# 18. Filter-active indicator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_active_indicator(app_with_deps):
    """Packages panel title should show filter text when filter is active."""
    from app import PackagesPanel
    from textual.widgets import Input

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()

        filter_input = app_with_deps.query_one("#filter-input", Input)
        filter_input.value = "http"
        await pilot.pause()

        await pilot.press("enter")  # close filter, keep text
        await pilot.pause()
        pkg_panel = app_with_deps.query_one("#packages-panel", PackagesPanel)
        title = str(pkg_panel.border_title or "")
        assert "filter" in title.lower()
        assert "http" in title.lower()


# ---------------------------------------------------------------------------
# 19. Enter on packages opens Update modal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enter_on_package_opens_update(app_with_deps):
    """Pressing Enter on a selected package should open the Update modal."""
    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        # Check if UpdatePackageModal is the current screen
        from app import UpdatePackageModal

        assert isinstance(app_with_deps.screen, UpdatePackageModal)


# ---------------------------------------------------------------------------
# 20. PEP 735 [dependency-groups] parsing
# ---------------------------------------------------------------------------


def test_parse_pyproject_dependency_groups(tmp_path):
    """PEP 735 [dependency-groups] should be parsed."""
    toml = tmp_path / "pyproject.toml"
    toml.write_text(
        textwrap.dedent("""\
        [project]
        name = "example"
        dependencies = ["requests>=2.31"]

        [dependency-groups]
        dev = ["pytest>=7.0", "ruff"]
        docs = ["sphinx>=7.0"]
    """)
    )
    from app import _parse_pyproject

    deps = _parse_pyproject(toml)
    names = [d[0] for d in deps]
    assert "requests" in names
    assert "pytest" in names
    assert "ruff" in names
    assert "sphinx" in names
    # Check dev group source label
    dev_deps = [d for d in deps if "dev" in d[2]]
    assert len(dev_deps) >= 2


# ---------------------------------------------------------------------------
# 21. Sync and Lock actions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Pressing ``s`` runs ``uv sync`` via the package manager."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    from app import DependencyManagerApp

    app = DependencyManagerApp()

    mock_sync = AsyncMock(return_value=(True, ""))

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        monkeypatch.setattr(app.pkg_mgr, "sync", mock_sync)
        await pilot.press("s")
        await pilot.pause()
        import asyncio

        await asyncio.sleep(0.3)
        await pilot.pause()
        mock_sync.assert_called_once()


@pytest.mark.asyncio
async def test_lock_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Pressing ``L`` runs ``uv lock`` via the package manager."""
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    from app import DependencyManagerApp

    app = DependencyManagerApp()

    mock_lock = AsyncMock(return_value=(True, ""))

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        monkeypatch.setattr(app.pkg_mgr, "lock", mock_lock)
        await pilot.press("L")
        await pilot.pause()
        import asyncio

        await asyncio.sleep(0.3)
        await pilot.pause()
        mock_lock.assert_called_once()


# ---------------------------------------------------------------------------
# 22. Update All Outdated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_all_outdated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Pressing ``U`` with outdated packages opens a ConfirmModal."""
    from app import ConfirmModal, DependencyManagerApp, _normalise

    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    app = DependencyManagerApp()

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        # Manually set latest versions so some packages appear outdated
        app._latest_versions = {
            _normalise("requests"): "99.0.0",
            _normalise("httpx"): "99.0.0",
            _normalise("click"): "99.0.0",
        }

        await pilot.press("U")
        await pilot.pause()

        # A ConfirmModal should have appeared
        assert isinstance(app.screen, ConfirmModal)


@pytest.mark.asyncio
async def test_update_all_outdated_none_outdated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Pressing ``U`` with no outdated packages shows a warning, no modal."""
    from app import ConfirmModal, DependencyManagerApp, _normalise

    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    app = DependencyManagerApp()

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        # Set latest versions to match installed (no outdated)
        app._latest_versions = {
            _normalise("requests"): "2.32.3",
            _normalise("httpx"): "0.28.1",
            _normalise("click"): "8.1.7",
        }

        await pilot.press("U")
        await pilot.pause()

        # No modal should appear — still on the main screen
        assert not isinstance(app.screen, ConfirmModal)


# ---------------------------------------------------------------------------
# 18. Dependency tree in Details panel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_details_shows_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Details panel should show dependency list from ``_get_package_requires``."""
    from app import DetailsPanel, DependencyManagerApp, PackagesPanel

    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "uv.lock").write_text(_UVLOCK)
    monkeypatch.chdir(tmp_path)

    async def mock_requires(name: str) -> list[str]:
        return ["certifi", "idna", "urllib3"]

    monkeypatch.setattr("app._get_package_requires", mock_requires)

    app = DependencyManagerApp()

    async with app.run_test(size=(140, 30)) as pilot:
        await pilot.pause()

        # Focus packages panel and select first package
        pkg_panel = app.query_one("#packages-panel", PackagesPanel)
        pkg_panel.focus()
        await pilot.pause()

        # Navigate to trigger details update
        await pilot.press("j")
        await pilot.pause()
        await pilot.press("k")
        await pilot.pause()

        details = app.query_one("#details-panel", DetailsPanel)
        rendered = str(details.render())

        # Should show the dependencies section
        assert "Dependencies" in rendered
        assert "certifi" in rendered
        assert "idna" in rendered
        assert "urllib3" in rendered


# ---------------------------------------------------------------------------
# 18. PyPI Search Modal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_pypi_modal_opens(app_with_deps):
    """Pressing p should open the PyPI search modal."""
    from app import SearchPyPIModal

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app_with_deps.screen, SearchPyPIModal)


@pytest.mark.asyncio
async def test_search_pypi_modal_escape_closes(app_with_deps):
    """Pressing Escape in the PyPI search modal should close it."""
    from app import SearchPyPIModal

    async with app_with_deps.run_test(size=(140, 30)) as pilot:
        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app_with_deps.screen, SearchPyPIModal)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app_with_deps.screen, SearchPyPIModal)


@pytest.mark.asyncio
async def test_search_pypi_parse_html():
    """``_parse_search_html`` should extract package info from HTML."""
    from app import SearchPyPIModal

    html = """
    <a class="package-snippet">
        <span class="package-snippet__name">requests</span>
        <span class="package-snippet__version">2.31.0</span>
        <p class="package-snippet__description">HTTP for Humans</p>
    </a>
    <a class="package-snippet">
        <span class="package-snippet__name">httpx</span>
        <span class="package-snippet__version">0.24.1</span>
        <p class="package-snippet__description">A next-gen HTTP client</p>
    </a>
    """
    results = SearchPyPIModal._parse_search_html(html)
    assert len(results) == 2
    assert results[0] == ("requests", "2.31.0", "HTTP for Humans")
    assert results[1] == ("httpx", "0.24.1", "A next-gen HTTP client")
