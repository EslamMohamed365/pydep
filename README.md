# PyDep

A fully keyboard-driven terminal UI for managing Python project dependencies, powered by [uv](https://docs.astral.sh/uv/) and themed with the [Tokyo Night](https://github.com/enkia/tokyo-night-vscode-theme) color palette.

PyDep scans your project for dependencies across multiple sources — `pyproject.toml`, `requirements.txt`, `setup.py`, `setup.cfg`, `Pipfile`, and installed packages — and presents them in a lazygit-style multi-panel interface with Vim-style navigation.

![PyDep Demo](demo.gif)

## Features

- **Lazygit-style layout** — Multi-panel interface with Status, Sources, Packages, and Details panels. Navigate between panels with `Tab` or number keys (`1`/`2`/`3`)
- **Multi-source scanning** — Aggregates dependencies from 6 sources into a single view, merging duplicates by normalized name (PEP 503)
- **Source filtering** — Select a source in the Sources panel to filter the Packages panel to only that source's dependencies
- **Vim-style navigation** — `j`/`k` movement, `gg` jump to top, `G` jump to bottom, `/` filter mode
- **Keyboard-first** — No mouse required. Every action has a keybinding
- **PyPI validation** — Async package/version verification before any install or update. Leave version blank to auto-resolve the latest
- **Outdated check** — Batch-query PyPI for the latest version of every package. Color-coded: green = up to date, yellow = outdated
- **Source-aware deletion** — Remove a package from a specific source file. Multi-source packages prompt you to choose which source
- **Virtual environment creation** — Press `v` to create a `.venv` via `uv venv`
- **Loading indicators** — Visual feedback during all async operations (refresh, add, update, delete, outdated check, venv creation)
- **uv integration** — Uses `uv add`, `uv remove`, `uv venv`, and `uv pip` under the hood
- **Tokyo Night theme** — Consistent dark color palette across all UI elements
- **Contextual hints** — Bottom hint bar updates based on which panel is focused

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) on your `PATH`

## Installation

```bash
git clone https://github.com/EslamMohamed365/pydep.git
cd pydep
uv sync
```

## Usage

```bash
uv run python app.py
```

If no `pyproject.toml` exists in the current directory, PyDep will offer to initialize one via `uv init --bare`.

## Layout

```
┌─ Status ──────────┐┌─ Details ──────────────────────────────┐
│ PyDep v0.1.0       ││ Package: httpx                         │
│ Python 3.13.11     ││ Installed: 0.27.0                      │
│ uv 0.7.12          ││ Latest: 0.28.1                         │
│ .venv ✓            ││ Status: Outdated                       │
│ 12 packages        ││                                        │
│ 3 sources          ││ Sources:                               │
│ 2 outdated         ││   pyproject.toml: >=0.27.0             │
├─ Sources ─────────┤│   requirements.txt: httpx==0.27.0      │
│ ▸ All Sources      ││                                        │
│   pyproject.toml   ││                                        │
│   requirements.txt ││                                        │
├─ Packages ────────┤│                                        │
│ ▸ httpx    0.27.0  ││                                        │
│   rich     13.9.4  ││                                        │
│   textual  1.0.0   ││                                        │
└────────────────────┘└────────────────────────────────────────┘
 Tab:switch  j/k:nav  /:filter  a:add  d:del  u:upd  ?:help
```

## Keybindings

### Panel Navigation

| Key | Action |
|-----|--------|
| `Tab` / `Shift+Tab` | Cycle panel focus forward / backward |
| `1` | Jump to Status panel |
| `2` | Jump to Sources panel |
| `3` | Jump to Packages panel |

### Within a Panel (Sources / Packages)

| Key | Action |
|-----|--------|
| `j` / `k` | Move selection down / up |
| `G` | Jump to last item |
| `g g` | Jump to first item |
| `Enter` | Select source (Sources panel) |

### Global Actions

| Key | Action |
|-----|--------|
| `/` | Open filter bar (filters packages by name) |
| `a` | Add a package |
| `u` | Update selected package |
| `d` | Delete selected package |
| `o` | Check outdated packages |
| `r` | Refresh package list |
| `v` | Create virtual environment (`uv venv`) |
| `i` | Initialize project (`uv init --bare`) |
| `?` | Toggle help overlay |
| `q` | Quit |

### Filter Mode

| Key | Action |
|-----|--------|
| *any text* | Filter packages by name |
| `Escape` | Clear filter and close |
| `Enter` | Close filter (keep text) |

### Modals

| Key | Action |
|-----|--------|
| `Tab` | Next field |
| `Enter` | Submit |
| `Escape` | Cancel |
| `y` / `n` | Yes / No (confirmation dialogs) |

## Supported Dependency Sources

| Source | Parsed | Removal |
|--------|--------|---------|
| `pyproject.toml` | `[project].dependencies` + optional groups | `uv remove` |
| `requirements*.txt` | Line-by-line (skips comments/flags) | Line removal |
| `setup.py` | AST-based `install_requires` extraction | Manual only (toast warning) |
| `setup.cfg` | `[options].install_requires` via configparser | configparser edit |
| `Pipfile` | `[packages]` + `[dev-packages]` via TOML | Key removal |
| Virtual environment | `uv pip list --format json` | `uv pip uninstall` |

## Project Structure

```
pydep/
  app.py          # Application code: data model, parsers, panel widgets, modals, TUI
  app.tcss        # Tokyo Night themed Textual CSS for multi-panel layout
  test_app.py     # 67 headless tests (Textual pilot)
  pyproject.toml  # Project metadata and dependencies
  demo.tape       # VHS script for generating the demo GIF
```

## Testing

```bash
uv run pytest test_app.py -v
```

67 tests covering:

- All 6 dependency parsers (including missing-file edge cases)
- Multi-source merge logic
- PyPI validation (4 scenarios)
- Panel existence and layout
- Status panel info display and venv status
- Sources panel population and source selection filtering
- Details panel updates on package selection
- Vim motions (`j`/`k`/`G`/`gg`) in Packages and Sources panels
- Tab cycling and number-key panel jumping
- Filter mode (open, close, escape, filtering)
- Contextual hint bar updates
- All modal interactions
- Per-source removal functions
- Source-aware deletion flow (single-source vs multi-source)
- Outdated check (batch query, UI integration, status panel count)
- Venv creation warning
- Loading overlay

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes and add tests
4. Run the test suite (`uv run pytest test_app.py -v`)
5. Commit and open a pull request

## License

MIT
