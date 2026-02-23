# AGENTS.md — PyDep

## Project Overview

PyDep is a single-file TUI application for managing Python project dependencies.
It wraps `uv` and uses the Textual framework with a lazygit-style multi-panel
interface and Vim keybindings. Python 3.13+ required.

**Key files:**
- `app.py` — entire application (~2650 lines)
- `app.tcss` — Textual CSS stylesheet (Tokyo Night theme)
- `test_app.py` — all tests (~2580 lines, 108 tests)
- `pyproject.toml` — project metadata and dependencies

This is NOT a package — no `src/`, no `__init__.py`, no build backend.
Run directly with `python app.py` or `uv run python app.py`.

---

## Build / Run / Test Commands

```bash
# Install dependencies
uv sync

# Run the application
uv run python app.py

# Run all tests (verbose)
uv run pytest test_app.py -v

# Run a single test by name substring
uv run pytest test_app.py -v -k "test_parse_pyproject"

# Run a single test by exact node ID
uv run pytest test_app.py::test_parse_pyproject -v

# Lint (ruff defaults — no config in pyproject.toml)
uv run ruff check app.py test_app.py

# Format
uv run ruff format app.py test_app.py
```

There is no Makefile, tox.ini, or CI pipeline. The only GitHub Actions workflow
is `.github/workflows/opencode.yml` (AI agent trigger).

---

## Code Style Guidelines

### Imports

1. `from __future__ import annotations` — always first (enables PEP 604 `X | Y`).
2. Standard library imports (alphabetical within group).
3. Third-party imports (`requests`, `textual`).
4. Groups separated by a single blank line.
5. No relative imports (single-module project).

```python
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import ClassVar

import requests
from textual.app import App
from textual.widgets import Static
```

### Formatting

- **Line length:** ~88–95 characters (Ruff defaults, no explicit config).
- **Formatter/linter:** Ruff only (`ruff format`, `ruff check`). No Black/isort/flake8.
- **Strings:** f-strings exclusively. Never `.format()` or `%`.
- **Multi-line strings:** `"""..."""` with `textwrap.dedent` in tests.
- **Line continuation:** Use `(`, `[`, `{` for multi-line expressions, not `\`.

### Type Annotations

Every function/method must have full annotations including return types.

- PEP 604 unions: `str | None`, not `Optional[str]`.
- Lowercase generics: `list[str]`, `dict[str, str]`, `tuple[bool, str]`.
- `ClassVar` for class-level constants.
- `-> None` for void methods.
- Textual reactives: `reactive[str]`, `reactive[int]`, `reactive[bool]`.

### Naming Conventions

| Element            | Convention              | Example                        |
|--------------------|-------------------------|--------------------------------|
| Functions/methods  | `snake_case`            | `load_dependencies`, `move_up` |
| Private functions  | `_snake_case`           | `_normalise`, `_parse_lock`    |
| Classes            | `PascalCase`            | `PackageManager`, `DetailsPanel` |
| Module constants   | `_UPPER_SNAKE_CASE`     | `_DEP_RE`, `_SOURCE_COLORS`    |
| Class constants    | `UPPER_SNAKE_CASE`      | `TITLE`, `CSS_PATH`, `BINDINGS` |
| Private attributes | `self._name`            | `self._uv`, `self._filter`    |
| Test functions     | `test_descriptive_name` | `test_vim_j_k_in_packages`    |
| Test fixtures      | `snake_case`            | `app_with_deps`, `app_no_deps` |

### Docstrings

Sphinx/reST-lite style — single-line or short multi-line. No Google-style
`Args:`/`Returns:` sections. Double backticks for inline code references.

```python
"""Run a ``uv`` command and capture combined output."""
"""Returns ``(is_valid, error_message, resolved_version)``."""
```

### Classes and Data Structures

- `@dataclass` for data-holding structures (`DepSource`, `Package`).
- No attrs, pydantic, NamedTuple, or TypedDict.
- Textual widgets inherit from `Static` or `ModalScreen`; panels share `PanelWidget(Static)`.

### Error Handling

1. No custom exceptions — built-in only.
2. `RuntimeError` for fatal preconditions (e.g., `uv` not found).
3. Return tuples for signaling: `tuple[bool, str]` → `(success, message)`.
4. Broad `except Exception` returning empty defaults for best-effort parsing
   (intentional — malformed files must not crash the UI).
5. `except requests.RequestException` for network errors.
6. `self.notify(..., severity="error")` for user-facing errors.

### Async Patterns

- `asyncio.create_subprocess_exec` for `uv` commands.
- `asyncio.gather` for parallel HTTP requests.
- `asyncio.Semaphore(10)` for rate-limiting concurrent PyPI queries.
- `asyncio.to_thread(requests.get, ...)` to run sync HTTP in threads.
- Textual `@work(exclusive=True, group="...")` for background tasks.

### Testing Patterns

- **Framework:** pytest + pytest-asyncio.
- **Async tests:** `@pytest.mark.asyncio` decorator.
- **Fixtures:** `@pytest.fixture` with `tmp_path` and `monkeypatch`.
- **TUI testing:** Textual `app.run_test()` headless pilot.
- **Mocking:** `unittest.mock.AsyncMock` and `monkeypatch.setattr`.
- **Network isolation:** `autouse` fixture patches `requests.get` globally — no test
  makes real HTTP calls.
- **Tests grouped** by feature area with `# ---` section headers.

```python
@pytest.mark.asyncio
async def test_vim_j_k_in_packages(app_with_deps):
    async with app_with_deps.run_test() as pilot:
        await pilot.press("j")
        ...
```

### Section Organization in app.py

Major sections use banner comments — place new code in the appropriate section:

```python
# =============================================================================
# Section Name
# =============================================================================
```

Sections (in order): Data Structures → Package Manager → Dependency Parsing →
Per-source Removal Helpers → PyPI Validation → Environment Info Helpers →
Panel Widgets → Source Color Helper → Modal Screens → Main Application →
Entry Point.
