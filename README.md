# PyDep

A fully keyboard-driven terminal UI for managing Python project dependencies, powered by [uv](https://docs.astral.sh/uv/) and themed with the [Tokyo Night](https://github.com/enkia/tokyo-night-vscode-theme) color palette.

PyDep scans your project for dependencies across multiple sources — `pyproject.toml`, `requirements.txt`, `setup.py`, `setup.cfg`, `Pipfile`, and installed packages — and presents them in a unified, searchable table with Vim-style navigation.

## Features

- **Multi-source scanning** — Aggregates dependencies from 6 sources into a single view, merging duplicates by normalized name (PEP 503)
- **Vim-style navigation** — `j`/`k` movement, `gg` jump to top, `G` jump to bottom, `/` incremental search
- **Keyboard-first** — No mouse required. Every action has a keybinding
- **PyPI validation** — Async package/version verification before any install or update. Leave version blank to auto-resolve the latest
- **Source-aware deletion** — Remove a package from a specific source file. Multi-source packages prompt you to choose which source
- **uv integration** — Uses `uv add`, `uv remove`, and `uv pip` under the hood
- **Tokyo Night theme** — Consistent dark color palette across all UI elements

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

## Keybindings

### Normal Mode (table focused)

| Key | Action |
|-----|--------|
| `j` / `k` | Move cursor down / up |
| `G` | Jump to last row |
| `g g` | Jump to first row |
| `/` | Enter search mode |
| `a` | Add a package |
| `u` | Update selected package |
| `d` | Delete selected package |
| `r` | Refresh package list |
| `i` | Initialize project (`uv init --bare`) |
| `?` | Toggle help overlay |
| `q` | Quit |

### Search Mode (search bar focused)

| Key | Action |
|-----|--------|
| *any text* | Filter packages by name or source file |
| `Escape` | Return to table |
| `Enter` | Return to table |

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
  app.py          # Application code: data model, parsers, modals, TUI
  app.tcss        # Tokyo Night themed Textual CSS
  test_app.py     # 49 headless tests (Textual pilot)
  pyproject.toml  # Project metadata and dependencies
```

## Testing

```bash
uv run pytest test_app.py -v
```

49 tests covering:

- All 6 dependency parsers (including missing-file edge cases)
- Multi-source merge logic
- PyPI validation (4 scenarios)
- Vim motions and search filtering
- All modal interactions
- Per-source removal functions
- Source-aware deletion flow (single-source vs multi-source)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes and add tests
4. Run the test suite (`uv run pytest test_app.py -v`)
5. Commit and open a pull request

## License

MIT
