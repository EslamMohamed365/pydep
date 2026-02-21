# AGENTS.md — PyDep

## Project Overview

PyDep is a single-file Terminal User Interface (TUI) application for managing Python
project dependencies. It wraps `uv` and uses the Textual framework with a lazygit-style
multi-panel interface and Vim keybindings. Python 3.13+ required.

**Key files:**
- `app.py` — entire application (~1950 lines)
- `app.tcss` — Textual CSS stylesheet (Tokyo Night theme)
- `test_app.py` — all tests (~1520 lines, 67+ tests)
- `pyproject.toml` — project metadata and dependencies

This is NOT a package — there is no `src/` directory, no `__init__.py`, no build backend.
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

# Run a single test by name
uv run pytest test_app.py -v -k "test_parse_pyproject"

# Run a single test by node ID
uv run pytest test_app.py::test_parse_pyproject -v

# Lint (ruff, using defaults — no config in pyproject.toml)
uv run ruff check app.py test_app.py

# Format
uv run ruff format app.py test_app.py
```

There is no Makefile, tox.ini, or CI test pipeline. The only GitHub Actions workflow
is `.github/workflows/opencode.yml` for an AI agent trigger.

---

## Code Style Guidelines

### Imports

1. `from __future__ import annotations` — always first line (enables PEP 604 `X | Y`).
2. Standard library imports (alphabetical within group).
3. Third-party imports (`httpx`, `rich`, `textual`).
4. Separate groups with a single blank line.
5. No relative imports (single-module project).

```python
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import httpx
from textual.app import App
from textual.widgets import Static
```

### Formatting

- **Line length:** ~88–95 characters (Ruff defaults, no explicit config).
- **Formatter:** Ruff (`ruff format`). No Black, isort, or other tools.
- **Linter:** Ruff (`ruff check`). No flake8 or pylint.
- **String formatting:** f-strings exclusively. Never use `.format()` or `%`.
- **Multi-line strings:** Triple-quoted `"""..."""` with `textwrap.dedent` in tests.
- **Implicit line continuation:** Use `(`, `[`, `{` for multi-line expressions, not `\`.

### Type Annotations

Every function and method must have full type annotations, including return types.

- Use PEP 604 union syntax: `str | None`, not `Optional[str]`.
- Use lowercase generics: `list[str]`, `dict[str, str]`, `tuple[bool, str]`.
- Use `ClassVar` from `typing` for class-level constants.
- Use `-> None` for void methods.
- Textual reactives: `reactive[str]`, `reactive[int]`, `reactive[bool]`.

```python
def _parse_dep_string(raw: str) -> tuple[str, str]:
    ...

async def validate_pypi(name: str) -> tuple[bool, str | None, str | None]:
    ...
```

### Naming Conventions

| Element              | Convention            | Example                          |
|----------------------|-----------------------|----------------------------------|
| Functions/methods    | `snake_case`          | `load_dependencies`, `move_up`   |
| Private functions    | `_snake_case`         | `_normalise`, `_parse_lock`      |
| Classes              | `PascalCase`          | `PackageManager`, `DetailsPanel` |
| Module constants     | `_UPPER_SNAKE_CASE`   | `_DEP_RE`, `_SOURCE_COLORS`      |
| Class constants      | `UPPER_SNAKE_CASE`    | `TITLE`, `CSS_PATH`, `BINDINGS`  |
| Private attributes   | `self._name`          | `self._uv`, `self._filter`      |
| Test functions       | `test_descriptive_name` | `test_vim_j_k_in_packages`     |
| Test fixtures        | `snake_case`          | `app_with_deps`, `app_no_deps`   |

### Docstrings

Use Sphinx/reST-lite style — single-line or short multi-line. No Google-style
`Args:`/`Returns:` sections. Use double backticks for inline code references.

```python
"""Run a ``uv`` command and capture combined output."""

"""PEP 503 normalisation (lowercase, hyphens/underscores/dots -> -)."""

"""Returns ``(is_valid, error_message, resolved_version)``."""
```

### Classes and Data Structures

- **Data classes:** Use `@dataclass` for data-holding structures (`DepSource`, `Package`).
- **No attrs, pydantic, NamedTuple, or TypedDict** — keep it simple.
- **Inheritance:** Textual widgets inherit from `Static` or `ModalScreen`.
  Panel widgets share a base class `PanelWidget(Static)`.
- **Keyword-only args:** Use `*` separator for clarity in constructors.

```python
@dataclass
class Package:
    name: str
    sources: list[DepSource]
    version: str | None = None
```

### Error Handling

1. **No custom exceptions.** Use built-in exceptions only.
2. **`RuntimeError`** for fatal precondition failures (e.g., `uv` not found).
3. **Return tuples for error signaling:** `tuple[bool, str]` — `(success, message)`.
4. **Broad `except Exception`** that returns empty defaults for best-effort parsing.
   This is intentional — malformed files should not crash the UI.
5. **Specific exceptions** for network errors: `except httpx.HTTPError as exc:`.
6. **TUI notifications** for user-facing errors: `self.notify(..., severity="error")`.

```python
# Return-based error signaling
async def _run(self, *args: str) -> tuple[bool, str]:
    ...
    return proc.returncode == 0, output.strip()

# Best-effort parsing
try:
    data = tomllib.loads(text)
except Exception:
    return []
```

### Async Patterns

- `asyncio.create_subprocess_exec` for running `uv` commands.
- `asyncio.gather` for parallel HTTP requests.
- `asyncio.Semaphore(10)` for rate-limiting concurrent PyPI queries.
- Textual `@work(exclusive=True, group="...")` for background async tasks.

### Testing Patterns

- **Framework:** pytest + pytest-asyncio.
- **Async tests:** `@pytest.mark.asyncio` decorator.
- **Fixtures:** `@pytest.fixture` with `tmp_path` and `monkeypatch`.
- **TUI testing:** Textual's `app.run_test()` headless pilot.
- **Mocking:** `unittest.mock.AsyncMock` and `monkeypatch.setattr`.
- **Test structure:** Tests are grouped by feature area with comment section headers.

```python
@pytest.mark.asyncio
async def test_vim_j_k_in_packages(app_with_deps):
    async with app_with_deps.run_test() as pilot:
        await pilot.press("j")
        ...
```

### Section Organization in app.py

Major sections are separated by banner comments:

```python
# ================================================================
# Section Name
# ================================================================
```

Keep this organization when adding new code. Place new functions/classes in the
appropriate section rather than appending to the end of the file.
