<div align="center">

<h1>PyDep</h1>

<p><strong>A fully keyboard-driven terminal UI for multi-language dependency management</strong></p>

<p><em>Python, JavaScript & Go support &nbsp;&middot;&nbsp; lazygit-style panels &nbsp;&middot;&nbsp; Vim keybindings &nbsp;&middot;&nbsp; Tokyo Night theme</em></p>

<br>

[![Python](https://img.shields.io/badge/python-3.13+-blue?style=flat-square&logo=python&logoColor=white&color=7aa2f7)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square&color=9ece6a)](LICENSE)
[![uv](https://img.shields.io/badge/uv-powered-orange?style=flat-square&color=e0af68)](https://docs.astral.sh/uv/)
[![Textual](https://img.shields.io/badge/built%20with-Textual-purple?style=flat-square&color=bb9af7)](https://textual.textualize.io/)
[![Tests](https://img.shields.io/badge/tests-123%20passing-brightgreen?style=flat-square&color=9ece6a)](test_app.py)

<br>

![PyDep Demo](demo.gif)

</div>

---

## What is PyDep?

PyDep is a **multi-language dependency manager** that supports **Python** (`pyproject.toml`, `requirements.txt`, etc.), **JavaScript** (`package.json`), and **Go** (`go.mod`). It scans your project for dependencies across all sources and presents them in a unified, lazygit-inspired multi-panel interface.

No mouse. No menus. Just your keyboard, Vim motions, and instant access to everything.

**Why PyDep instead of running package manager commands manually?**

- **See everything at once** &mdash; all sources, versions, and outdated status in a single view
- **Discover & install in seconds** &mdash; fuzzy-search the registry, browse results with <kbd>j</kbd>/<kbd>k</kbd>, install without leaving the terminal
- **Works with any project layout** &mdash; understands multiple dependency formats and languages simultaneously
- **Switch languages instantly** &mdash; press <kbd>e</kbd> to cycle between Python, JavaScript, and Go

---

## Installation

**Prerequisites**

| Requirement | Version | Install |
|-------------|---------|---------|
| Python | 3.13+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

**Setup**

```bash
git clone https://github.com/EslamMohamed365/pydep.git
cd pydep
uv sync
```

**Run** (from your project's directory):

```bash
uv run python /path/to/pydep/app.py
```

> **Note:** Run `app.py` from the directory containing your dependency files (`pyproject.toml`, `requirements.txt`, etc.). If no `pyproject.toml` exists, PyDep will offer to run `uv init --bare` for you.

---

## Usage

### Common Tasks

| Task | Keys |
|------|------|
| **Add a package** | <kbd>a</kbd> &rarr; type name + optional version &rarr; confirm |
| **Search PyPI** | <kbd>p</kbd> &rarr; type query &rarr; <kbd>j</kbd>/<kbd>k</kbd> to browse &rarr; <kbd>Enter</kbd> |
| **Check outdated** | <kbd>o</kbd> &mdash; green = current, yellow = outdated |
| **Update all outdated** | <kbd>U</kbd> after running the outdated check |
| **Remove a package** | <kbd>d</kbd> &mdash; multi-source packages prompt which source |
| **Filter packages** | <kbd>/</kbd> &rarr; start typing &mdash; live filter by name |
| **Open package docs** | <kbd>D</kbd> &mdash; opens PyPI page in your browser |
| **Sync environment** | <kbd>s</kbd> &mdash; runs `uv sync` |

### Keybindings

<details>
<summary><strong>Panel Navigation</strong></summary>

| Key | Action |
|-----|--------|
| <kbd>Tab</kbd> / <kbd>Shift+Tab</kbd> | Cycle panel focus forward / backward |
| <kbd>1</kbd> | Jump to Status panel |
| <kbd>2</kbd> | Jump to Sources panel |
| <kbd>3</kbd> | Jump to Packages panel |

</details>

<details>
<summary><strong>Within Sources / Packages</strong></summary>

| Key | Action |
|-----|--------|
| <kbd>j</kbd> / <kbd>k</kbd> | Move selection down / up |
| <kbd>G</kbd> | Jump to last item |
| <kbd>g</kbd> <kbd>g</kbd> | Jump to first item |
| <kbd>Enter</kbd> | Select source / Update package |

</details>

<details>
<summary><strong>Global Actions</strong></summary>

| Key | Action |
|-----|--------|
| <kbd>e</kbd> | Cycle to next ecosystem (Python → JavaScript → Go) |
| <kbd>E</kbd> | Cycle to previous ecosystem |
| <kbd>/</kbd> | Open filter bar |
| <kbd>a</kbd> | Add a package |
| <kbd>p</kbd> | Search registry |
| <kbd>u</kbd> | Update selected package |
| <kbd>d</kbd> | Delete selected package |
| <kbd>o</kbd> | Check for outdated packages |
| <kbd>U</kbd> | Update **all** outdated packages |
| <kbd>s</kbd> | Sync dependencies |
| <kbd>L</kbd> | Lock dependencies |
| <kbd>D</kbd> | Open package docs in browser |
| <kbd>r</kbd> | Refresh package list |
| <kbd>v</kbd> | Create virtual environment |
| <kbd>i</kbd> | Initialize project |
| <kbd>?</kbd> | Toggle help overlay |
| <kbd>q</kbd> | Quit |

</details>

<details>
<summary><strong>Filter Mode & Modals</strong></summary>

**Filter Mode**

| Key | Action |
|-----|--------|
| *type* | Filter packages by name in real time |
| <kbd>Escape</kbd> | Clear filter and close |
| <kbd>Enter</kbd> | Close filter bar (keep active filter) |

**Modals**

| Key | Action |
|-----|--------|
| <kbd>Tab</kbd> | Next field |
| <kbd>Enter</kbd> | Submit |
| <kbd>Escape</kbd> | Cancel |
| <kbd>y</kbd> / <kbd>n</kbd> | Yes / No in confirmation dialogs |

</details>

---

## Architecture

PyDep uses an **Ecosystem Adapter pattern** to support multiple programming languages. The architecture consists of:

- **`app.py`** &mdash; The TUI layer (panels, modals, keybindings)
- **`base.py`** &mdash; Abstract `Ecosystem` interface and data structures
- **`ecosystems/`** &mdash; Language-specific implementations:
  - `python.py` &mdash; Python/uv/PyPI
  - `javascript.py` &mdash; JavaScript/npm/npmjs.org
  - `go.py` &mdash; Go/goproxy.org

### Supported Languages

| Language | Package Manager | Registry | Files Scanned |
|----------|---------------|----------|---------------|
| **Python** | uv | PyPI | `pyproject.toml`, `requirements.txt`, `setup.py`, `setup.cfg`, `Pipfile`, `uv.lock` |
| **JavaScript** | npm | npmjs.org | `package.json`, `package-lock.json`, `node_modules` |
| **Go** | go mod | proxy.golang.org | `go.mod`, `go.sum` |

### Layout

```text
┌─ Status ────────────┐ ┌─ Details ──────────────────────────────────┐
│ PyDep v0.1.0        │ │ Package: httpx                              │
│ Python 3.13.11      │ │ Installed: 0.27.0                           │
│ uv 0.7.12           │ │ Latest:    0.28.1                           │
│ .venv ✓             │ │ Status:    Outdated                         │
│ 12 packages         │ │                                             │
│  3 sources          │ │ Sources:                                    │
│  2 outdated         │ │   pyproject.toml:   >=0.27.0               │
├─ Sources ───────────┤ │   requirements.txt: httpx==0.27.0          │
│ ▸ All Sources       │ │                                             │
│   pyproject.toml    │ │ Summary:                                    │
│   requirements.txt  │ │   The next-generation HTTP client.          │
├─ Packages ──────────┤ │                                             │
│ ● httpx    0.27.0   │ │                                             │
│   rich     13.9.4   │ │                                             │
│   textual  1.0.0    │ └─────────────────────────────────────────────┘
└─────────────────────┘
  Tab:switch  j/k:nav  /:filter  a:add  d:del  u:upd  s:sync  p:search  ?:help
```

### Module Structure

```
pydep/
├── app.py          # Entire application (~2600 lines)
│   ├── Data layer      — @dataclass models (Package, DepSource)
│   ├── Parsers         — one parser per source format
│   ├── PackageManager  — uv subprocess wrapper, PyPI client
│   ├── Panel widgets   — PanelWidget base, Status/Sources/Packages/Details
│   ├── Modal screens   — Add, Search, Confirm, Help, SourceSelect
│   └── PackageManagerApp — Textual App subclass, keybinding dispatch
├── app.tcss        # Tokyo Night themed Textual CSS
├── test_app.py     # 109 headless tests via Textual pilot
├── pyproject.toml  # Project metadata and dependencies
└── demo.tape       # VHS script for generating the demo GIF
```

### Interaction Flow

```text
User input (keypress)
    │
    ▼
PackageManagerApp.action_*()
    │
    ├─ Navigation ──► PanelWidget.move_up() / move_down()
    │
    ├─ Mutation ───► ModalScreen (Add/Confirm/SourceSelect)
    │                    │
    │                    ▼
    │               PackageManager._run("uv", ...)
    │                    │
    │                    ▼
    │               Reload parsers ──► refresh all panels
    │
    └─ Query ──────► PackageManager.validate_pypi() / check_outdated()
                         │
                         ▼
                    httpx async ──► PyPI JSON API
                         │
                         ▼
                    Update Details panel + notifications
```

### Design Decisions

- **Single file** &mdash; keeps the project trivially installable (`python app.py`) with zero packaging overhead.
- **`uv` as sole backend** &mdash; no pip/poetry/pipenv code paths; uv handles add, remove, sync, lock, venv.
- **Best-effort parsing** &mdash; malformed files return empty results instead of crashing the UI. Broad `except Exception` is intentional.
- **PEP 503 normalization** &mdash; all package names are lowercased with hyphens/underscores/dots collapsed so duplicates merge correctly.
- **Async with semaphores** &mdash; PyPI queries use `asyncio.gather` with `Semaphore(10)` to avoid hammering the API.

---

## Capabilities

### Multi-Source Scanning

Aggregates dependencies from all 6 formats into one unified list, merging duplicates by PEP 503 normalized name.

| Source | Parsed content | Removal method |
|--------|---------------|----------------|
| `pyproject.toml` | `[project].dependencies`, optional groups, `[dependency-groups]` (PEP 735) | `uv remove` |
| `requirements*.txt` | Line-by-line (skips comments and flags) | Line removal |
| `setup.py` | `install_requires` via AST extraction | Manual (toast warning) |
| `setup.cfg` | `[options].install_requires` via configparser | configparser edit |
| `Pipfile` | `[packages]` + `[dev-packages]` via TOML | Key removal |
| Virtual env | `uv pip list --format json` | `uv pip uninstall` |

### Package Management

- **Source filtering** &mdash; select a source in the Sources panel to show only its packages
- **PEP 735 dependency groups** &mdash; full support for `[dependency-groups]` in `pyproject.toml`
- **Version constraint picker** &mdash; choose `==`, `>=`, or `~=` when adding or updating
- **Source-aware deletion** &mdash; multi-source packages prompt you to choose which source to remove from

### PyPI Integration

- **Interactive search** &mdash; press <kbd>p</kbd> to fuzzy-search PyPI, browse with <kbd>j</kbd>/<kbd>k</kbd>, install with <kbd>Enter</kbd>
- **Async validation** &mdash; every install/update is verified against PyPI before running
- **Outdated detection** &mdash; press <kbd>o</kbd> to batch-query all packages; green = current, yellow = outdated
- **Update all** &mdash; press <kbd>U</kbd> to update everything with a single confirmation

### uv Integration

- **Full command coverage** &mdash; `uv add`, `uv remove`, `uv sync`, `uv lock`, `uv venv`, `uv pip`
- **Sync & Lock** &mdash; <kbd>s</kbd> / <kbd>L</kbd>
- **Venv creation** &mdash; <kbd>v</kbd> to create `.venv` via `uv venv`
- **Auto-init** &mdash; offers `uv init --bare` when no `pyproject.toml` exists
- **Loading indicators** &mdash; visual feedback during every async operation

---

## Testing

```bash
# Run full suite
uv run pytest test_app.py -v

# Run a single test
uv run pytest test_app.py -v -k "test_parse_pyproject"

# Lint & format
uv run ruff check app.py test_app.py
uv run ruff format app.py test_app.py
```

**109 tests** covering parsers for all 6 sources, PEP 735 groups, PyPI validation, panel layout, Vim motions, Tab cycling, filter mode, all modals, source-aware deletion, outdated detection, update-all, PyPI search, sync/lock, venv creation, scroll-to-visible, and loading overlays.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `uv: command not found` | Install uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh`, then restart your shell |
| No packages shown | Run `app.py` from your project directory (containing `pyproject.toml` or `requirements.txt`), not from the pydep clone |
| PyPI search returns nothing | First search builds a local index (~500k names) from PyPI Simple API. Takes a few seconds; cached at `~/.cache/pydep/pypi_index.json` for 24h |

---

## Contributing

1. Fork the repository
2. Create a feature branch &mdash; `git checkout -b feature/my-feature`
3. Make your changes and add tests
4. Run the suite &mdash; `uv run pytest test_app.py -v`
5. Lint &mdash; `uv run ruff check app.py && uv run ruff format app.py`
6. Open a pull request

---

## License

MIT &mdash; see [LICENSE](LICENSE).

---

<div align="center">

*Built with [Textual](https://textual.textualize.io/) &middot; Powered by [uv](https://docs.astral.sh/uv/) &middot; Themed with [Tokyo Night](https://github.com/enkia/tokyo-night-vscode-theme)*

</div>
