# Multi-Language Support for PyDep

Date: 2026-02-22
Status: Approved

## Goals

- Add JavaScript/Node.js and Go support alongside Python.
- Keep PyDep as a single-file project originally, but now multi-file for better organization.
- Use an Ecosystem Adapter pattern to make the TUI layer language-agnostic.
- Auto-detect which language(s) are present in the project directory.
- Provide a vim-like single-ecosystem-at-a-time view with quick switching (`e` key).
- Maintain full feature parity: parsing, package management CLI, registry API, environment info.

## Non-goals

- Mixing multiple ecosystems in a single view (use `e` to switch instead).
- Supporting offline registry lookups beyond simple caching.
- Adding Rust/Ruby/etc. in this iteration (extensible architecture makes it easy later).

## Design

### 1. Project Structure

```
pydep/
├── app.py                      # Entry point + main TUI app (panels, modals, keybindings)
├── app.tcss                    # Textual CSS (unchanged)
├── base.py                     # Ecosystem abstract interface + shared data structures
├── ecosystems/
│   ├── __init__.py             # Auto-detection logic + ecosystem registry
│   ├── python.py               # PythonEcosystem (uv, PyPI, pyproject.toml, etc.)
│   ├── javascript.py           # JavaScriptEcosystem (npm, npmjs, package.json, etc.)
│   └── go.py                   # GoEcosystem (go CLI, proxy.golang.org, go.mod, etc.)
├── test_app.py                 # TUI integration tests
├── test_ecosystems.py          # Ecosystem-specific unit tests
├── pyproject.toml
└── uv.lock
```

### 2. Core Interface (`base.py`)

```python
# Data structures
@dataclass
class DepSource:
    file: str          # e.g. "pyproject.toml", "package.json", "go.mod"
    specifier: str     # e.g. ">=2.31", "^1.0.0", "v1.21.0"

@dataclass
class Package:
    name: str
    sources: list[DepSource]
    installed_version: str
    ecosystem: "Ecosystem"  # back-reference

@dataclass
class RegistryPackageInfo:
    name: str
    latest_version: str
    description: str
    license: str | None
    homepage: str | None
    author: str | None
    requires: str | None

@dataclass
class EnvInfo:
    language_name: str
    language_version: str
    tool_name: str
    tool_version: str
    env_label: str
    env_exists: bool

# Abstract interface
class Ecosystem(ABC):
    name: str                     # "python", "javascript", "go"
    display_name: str             # "Python", "JavaScript", "Go"
    source_colors: dict[str, str]
    source_abbrevs: dict[str, str]

    @abstractmethod
    def detect(self, path: Path) -> bool: ...

    @abstractmethod
    async def load_dependencies(self, path: Path) -> list[Package]: ...

    @abstractmethod
    async def init_project(self, path: Path) -> tuple[bool, str]: ...
    @abstractmethod
    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]: ...
    @abstractmethod
    async def remove(self, package: str, source: str, group: str | None = None) -> tuple[bool, str]: ...
    @abstractmethod
    async def sync(self) -> tuple[bool, str]: ...
    @abstractmethod
    async def lock(self) -> tuple[bool, str]: ...
    @abstractmethod
    async def create_env(self) -> tuple[bool, str]: ...

    @abstractmethod
    async def validate_package(self, name: str, version: str | None = None) -> tuple[bool, str, str]: ...
    @abstractmethod
    async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]: ...
    @abstractmethod
    async def search_registry(self, query: str) -> list[RegistryPackageInfo]: ...
    @abstractmethod
    async def fetch_package_metadata(self, name: str) -> dict[str, str]: ...
    @abstractmethod
    async def get_package_requires(self, name: str) -> list[str]: ...

    @abstractmethod
    async def get_env_info(self) -> EnvInfo: ...
    @abstractmethod
    def get_docs_url(self, name: str) -> str: ...
```

### 3. Ecosystem Implementations

#### Python Ecosystem (`ecosystems/python.py`)
- **Detection:** `pyproject.toml`, `requirements*.txt`, `setup.py`, `setup.cfg`, `Pipfile`
- **Parsers:** Move existing `_parse_pyproject()`, `_parse_requirements()`, `_parse_setup_py()`, `_parse_setup_cfg()`, `_parse_pipfile()`, `_parse_lock()`, `_parse_installed()`
- **Package Manager:** wraps `uv` (existing `PackageManager`)
- **Registry:** PyPI JSON API + Simple API (existing)
- **Source colors:** `pyproject.toml` → purple, `requirements` → cyan, `setup.py`/`setup.cfg` → yellow, `Pipfile` → green, `venv` → dim
- **Groups:** main (default), dev, test (from PEP 735 dependency-groups)

#### JavaScript Ecosystem (`ecosystems/javascript.py`)
- **Detection:** `package.json`
- **Parsers:** `_parse_package_json()` (dependencies, devDependencies, peerDependencies, optionalDependencies), `_parse_package_lock()`, `_parse_installed()` (npm list --json)
- **Package Manager:** wraps `npm` — `npm init -y`, `npm install <pkg>`, `npm install --save-dev <pkg>`, `npm uninstall <pkg>`, `npm install`, `npm update`
- **Registry:** npmjs.org API — `https://registry.npmjs.org/<pkg>` for metadata, `/v1/search` for search
- **Source colors:** `package.json` → green, `package-lock.json` → dim, `node_modules` → dim
- **Groups:** dependencies (main), devDependencies (dev), peerDependencies (peer), optionalDependencies (optional)

#### Go Ecosystem (`ecosystems/go.py`)
- **Detection:** `go.mod`
- **Parsers:** `_parse_go_mod()` (require blocks, direct vs indirect), `_parse_go_sum()`, `_parse_installed()` (`go list -m -json all`)
- **Package Manager:** wraps `go` CLI — `go mod init <name>`, `go get <module>@<version>`, `go get <module>@none` + `go mod tidy`, `go mod tidy`, `go mod download`
- **Registry:** proxy.golang.org — `/@v/list` for versions, `/@latest` for latest, pkg.go.dev for search
- **Source colors:** `go.mod` → cyan, `go.sum` → dim
- **Groups:** Go has no groups — always "main". Indirect deps marked as "indirect"

### 4. Auto-Detection (`ecosystems/__init__.py`)

```python
def detect_all(path: Path) -> list[Ecosystem]:
    """Scan directory, return list of detected ecosystems in priority order."""
    detected = []
    for eco in [PythonEcosystem(), JavaScriptEcosystem(), GoEcosystem()]:
        if eco.detect(path):
            detected.append(eco)
    return detected
```

### 5. TUI Changes (`app.py`)

#### Single Active Ecosystem View
- App shows one ecosystem at a time
- Title bar: `PyDep — [Python] 🐍` with indicator `(1:Py 2:JS 3:Go)`
- Status, Packages, Sources, Details all reflect the active ecosystem

#### Ecosystem Switching
| Key | Action |
|-----|--------|
| `e` | Cycle to next detected ecosystem |
| `E` (Shift+e) | Cycle to previous |
| `1`/`2`/`3` | Jump directly to ecosystem (when no panel focused — otherwise jumps panels) |

#### Multi-Language Projects
- On startup, auto-detect all present languages
- Start on first detected (Python → JavaScript → Go priority)
- Use `e` to switch between them
- Each ecosystem operates independently

#### Keybinding Changes
- `i` (init) → if no ecosystem detected, prompt: (p)ython, (j)avascript, (g)o
- `s` (sync) → runs sync on active ecosystem
- `L` (lock) → runs lock on active ecosystem
- `p` (search) → searches the active ecosystem's registry
- `a` (add) → adds to active ecosystem
- `d` (delete) → removes from active ecosystem

#### App Class Changes
```python
class DependencyManagerApp(App):
    def __init__(self):
        self._ecosystems: list[Ecosystem] = []
        self._active_ecosystem: Ecosystem | None = None
        self._packages: list[Package] = []
```

### 6. Error Handling

- **Tool not installed:** Show warning in StatusPanel, read-only mode for that ecosystem
- **Network errors:** Return empty defaults (match existing Python behavior)
- **Malformed files:** Broad `except Exception` → empty package list
- **Registry differences:** Handle npmjs vs PyPI vs proxy.golang.org API quirks per ecosystem

### 7. Testing Strategy

#### `test_ecosystems.py` (new)
- Per-ecosystem parser tests
- Registry validation tests (mocked)
- CLI command tests (mocked subprocess)

#### `test_app.py` (existing)
- Add ecosystem switching tests: `test_press_e_cycles_ecosystems()`
- Multi-language project fixture
- Ecosystem indicator tests

### 8. Cache Per Ecosystem

| Ecosystem | Cache path |
|-----------|------------|
| Python | `~/.cache/pydep/pypi_index.json` |
| JavaScript | `~/.cache/pydep/npm_index.json` |
| Go | `~/.cache/pydep/go_index.json` |

(End of design document)
