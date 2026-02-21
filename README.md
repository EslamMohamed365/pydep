<div align="center">

```
██████╗ ██╗   ██╗██████╗ ███████╗██████╗
██╔══██╗╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗
██████╔╝ ╚████╔╝ ██║  ██║█████╗  ██████╔╝
██╔═══╝   ╚██╔╝  ██║  ██║██╔══╝  ██╔═══╝
██║        ██║   ██████╔╝███████╗██║
╚═╝        ╚═╝   ╚═════╝ ╚══════╝╚═╝
```

**A fully keyboard-driven terminal UI for Python dependency management**

*lazygit-style panels · Vim keybindings · Tokyo Night theme · powered by uv*

<br>

[![Python](https://img.shields.io/badge/python-3.13+-blue?style=flat-square&logo=python&logoColor=white&color=7aa2f7)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square&color=9ece6a)](LICENSE)
[![uv](https://img.shields.io/badge/uv-powered-orange?style=flat-square&color=e0af68)](https://docs.astral.sh/uv/)
[![Textual](https://img.shields.io/badge/built%20with-Textual-purple?style=flat-square&color=bb9af7)](https://textual.textualize.io/)
[![Tests](https://img.shields.io/badge/tests-109%20passing-brightgreen?style=flat-square&color=9ece6a)](test_app.py)

</div>

---

<div align="center">

![PyDep Demo](demo.gif)

</div>

---

## ✦ What is PyDep?

PyDep scans your project for dependencies across **6 sources** — `pyproject.toml`, `requirements.txt`, `setup.py`, `setup.cfg`, `Pipfile`, and your virtual environment — and presents them in a unified, lazygit-inspired multi-panel interface.

No mouse. No menus. Just your keyboard, Vim motions, and instant access to everything.

---

## ✦ Features

### 🗂 Interface & Navigation

- **Lazygit-style layout** — Status, Sources, Packages, and Details panels, all in one view
- **Vim motions** — <kbd>j</kbd>/<kbd>k</kbd> to move, <kbd>gg</kbd> to jump to top, <kbd>G</kbd> to bottom, <kbd>/</kbd> to filter
- **Panel switching** — <kbd>Tab</kbd>/<kbd>Shift+Tab</kbd> to cycle panels, or jump directly with <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd>
- **Contextual hints** — Bottom hint bar always shows relevant keys for the focused panel
- **Tokyo Night theme** — Consistent dark color palette across every UI element

### 📦 Package Management

- **Multi-source scanning** — Aggregates all 6 sources into one view, merging duplicates by normalized name (PEP 503)
- **Source filtering** — Focus a source in the Sources panel to filter packages to only that source
- **PEP 735 dependency groups** — Full support for `[dependency-groups]` in `pyproject.toml`
- **Version constraint picker** — Choose `==`, `>=`, or `~=` when adding or updating
- **Source-aware deletion** — Multi-source packages prompt you to choose which source to remove from

### 🔍 PyPI Integration

- **Interactive search** — Press <kbd>p</kbd> to fuzzy-search PyPI, browse results with <kbd>j</kbd>/<kbd>k</kbd>, install with <kbd>Enter</kbd>
- **Async validation** — Every install/update is verified against PyPI before running. Leave version blank to auto-resolve latest
- **Outdated detection** — Press <kbd>o</kbd> to batch-query PyPI for all packages. Green = current, yellow = outdated
- **Update all outdated** — Press <kbd>U</kbd> to update everything at once with a single confirmation

### ⚡ uv Integration

- **All `uv` commands** — `uv add`, `uv remove`, `uv sync`, `uv lock`, `uv venv`, `uv pip` under the hood
- **Sync & Lock** — <kbd>s</kbd> to sync, <kbd>L</kbd> to lock
- **Venv creation** — Press <kbd>v</kbd> to create `.venv` via `uv venv`
- **Auto-init** — If no `pyproject.toml` exists, PyDep offers to run `uv init --bare`
- **Loading indicators** — Visual feedback during every async operation

---

## ✦ Quick Start

```bash
# 1. Clone
git clone https://github.com/EslamMohamed365/pydep.git
cd pydep

# 2. Install dependencies
uv sync

# 3. Run
uv run python app.py
```

---

## ✦ Layout

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

---

## ✦ Keybindings

### Panel Navigation

| Key | Action |
|-----|--------|
| <kbd>Tab</kbd> / <kbd>Shift+Tab</kbd> | Cycle panel focus forward / backward |
| <kbd>1</kbd> | Jump to Status panel |
| <kbd>2</kbd> | Jump to Sources panel |
| <kbd>3</kbd> | Jump to Packages panel |

### Within Sources / Packages

| Key | Action |
|-----|--------|
| <kbd>j</kbd> / <kbd>k</kbd> | Move selection down / up |
| <kbd>G</kbd> | Jump to last item |
| <kbd>g</kbd> <kbd>g</kbd> | Jump to first item |
| <kbd>Enter</kbd> | Select source · Update package |

### Global Actions

| Key | Action |
|-----|--------|
| <kbd>/</kbd> | Open filter bar |
| <kbd>a</kbd> | Add a package |
| <kbd>p</kbd> | Search PyPI |
| <kbd>u</kbd> | Update selected package |
| <kbd>d</kbd> | Delete selected package |
| <kbd>o</kbd> | Check for outdated packages |
| <kbd>U</kbd> | Update **all** outdated packages |
| <kbd>s</kbd> | Sync — `uv sync` |
| <kbd>L</kbd> | Lock — `uv lock` |
| <kbd>D</kbd> | Open package docs in browser |
| <kbd>r</kbd> | Refresh package list |
| <kbd>v</kbd> | Create virtual environment |
| <kbd>i</kbd> | Initialize project — `uv init --bare` |
| <kbd>?</kbd> | Toggle help overlay |
| <kbd>q</kbd> | Quit |

### Filter Mode

| Key | Action |
|-----|--------|
| *type* | Filter packages by name in real time |
| <kbd>Escape</kbd> | Clear filter and close |
| <kbd>Enter</kbd> | Close filter bar (keep active filter) |

### Modals

| Key | Action |
|-----|--------|
| <kbd>Tab</kbd> | Next field |
| <kbd>Enter</kbd> | Submit |
| <kbd>Escape</kbd> | Cancel |
| <kbd>y</kbd> / <kbd>n</kbd> | Yes / No in confirmation dialogs |

---

## ✦ Supported Dependency Sources

| Source | What is parsed | Removal method |
|--------|---------------|----------------|
| `pyproject.toml` | `[project].dependencies`, optional groups, `[dependency-groups]` (PEP 735) | `uv remove` |
| `requirements*.txt` | Line-by-line (skips comments and flags) | Line removal |
| `setup.py` | `install_requires` via AST extraction | Manual (toast warning) |
| `setup.cfg` | `[options].install_requires` via configparser | configparser edit |
| `Pipfile` | `[packages]` + `[dev-packages]` via TOML | Key removal |
| Virtual environment | `uv pip list --format json` | `uv pip uninstall` |

---

## ✦ Project Structure

```
pydep/
├── app.py          # Entire application — parsers, panels, modals, TUI (~2600 lines)
├── app.tcss        # Tokyo Night themed Textual CSS for the multi-panel layout
├── test_app.py     # 109 headless tests via Textual pilot
├── pyproject.toml  # Project metadata and dependencies
└── demo.tape       # VHS script for generating the demo GIF
```

This is **not a package** — no `src/` layout, no `__init__.py`. Run directly with `uv run python app.py`.

---

## ✦ Testing

```bash
uv run pytest test_app.py -v
```

**109 tests** covering parsers for all 6 sources, PEP 735 groups, PyPI validation, panel layout, Vim motions, Tab cycling, filter mode, all modals, source-aware deletion, outdated detection, update-all, PyPI search, sync/lock, venv creation, scroll-to-visible, and loading overlays.

---

## ✦ Requirements

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** on your `PATH`

---

## ✦ Contributing

1. Fork the repository
2. Create a feature branch — `git checkout -b feature/my-feature`
3. Make your changes and add tests
4. Run the suite — `uv run pytest test_app.py -v`
5. Lint — `uv run ruff check app.py && uv run ruff format app.py`
6. Open a pull request

---

## ✦ License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

*Built with [Textual](https://textual.textualize.io/) · Powered by [uv](https://docs.astral.sh/uv/) · Themed with [Tokyo Night](https://github.com/enkia/tokyo-night-vscode-theme)*

</div>
