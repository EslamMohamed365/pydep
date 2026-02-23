# Multi-Language Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add JavaScript/Node.js and Go support to PyDep using an Ecosystem Adapter pattern with vim-like ecosystem switching.

**Architecture:** Extract current Python-specific logic into an abstract Ecosystem interface. Create three implementations (Python, JavaScript, Go). Make TUI ecosystem-agnostic with `e` key to cycle between languages.

**Tech Stack:** Python 3.13+, Textual 8+, requests, asyncio. No new dependencies.

---

## Phase 1: Core Infrastructure

### Task 1: Create `base.py` with abstract Ecosystem interface

**Files:**
- Create: `base.py`

**Step 1: Create base.py with data structures and abstract class**

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DepSource:
    """One place a dependency was declared."""
    file: str
    specifier: str


@dataclass
class Package:
    """Aggregated dependency across all sources."""
    name: str
    sources: list[DepSource]
    installed_version: str
    ecosystem: Ecosystem | None = None


@dataclass
class RegistryPackageInfo:
    """Metadata from package registry."""
    name: str
    latest_version: str
    description: str
    license: str | None = None
    homepage: str | None = None
    author: str | None = None
    requires: str | None = None


@dataclass
class EnvInfo:
    """Environment information for an ecosystem."""
    language_name: str
    language_version: str
    tool_name: str
    tool_version: str
    env_label: str
    env_exists: bool


class Ecosystem(ABC):
    """Abstract base for package ecosystems (Python, JavaScript, Go, etc.)."""

    name: str
    display_name: str
    source_colors: dict[str, str]
    source_abbrevs: dict[str, str]

    @abstractmethod
    def detect(self, path: Path) -> bool:
        """Return True if this ecosystem's files exist in `path`."""

    @abstractmethod
    async def load_dependencies(self, path: Path) -> list[Package]:
        """Scan `path` for all dependency sources, return merged list."""

    @abstractmethod
    async def init_project(self, path: Path) -> tuple[bool, str]:
        """Initialize a new project. Returns (success, message)."""

    @abstractmethod
    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        """Add a package. Returns (success, message)."""

    @abstractmethod
    async def remove(self, package: str, source: str, group: str | None = None) -> tuple[bool, str]:
        """Remove a package. Returns (success, message)."""

    @abstractmethod
    async def sync(self) -> tuple[bool, str]:
        """Sync dependencies. Returns (success, message)."""

    @abstractmethod
    async def lock(self) -> tuple[bool, str]:
        """Lock dependencies. Returns (success, message)."""

    @abstractmethod
    async def create_env(self) -> tuple[bool, str]:
        """Create environment/venv. Returns (success, message)."""

    @abstractmethod
    async def validate_package(self, name: str, version: str | None = None) -> tuple[bool, str, str]:
        """Validate package exists on registry. Returns (valid, error, resolved_version)."""

    @abstractmethod
    async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
        """Fetch latest version for each package name. Returns {name: version}."""

    @abstractmethod
    async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
        """Search registry for packages matching query."""

    @abstractmethod
    async def fetch_package_metadata(self, name: str) -> dict[str, str]:
        """Fetch full metadata for a package."""

    @abstractmethod
    async def get_package_requires(self, name: str) -> list[str]:
        """Get list of dependencies for a package."""

    @abstractmethod
    async def get_env_info(self) -> EnvInfo:
        """Get environment information."""

    @abstractmethod
    def get_docs_url(self, name: str) -> str:
        """Get documentation URL for a package."""
```

**Step 2: Commit**

```bash
git add base.py
git commit -m "feat: add base.py with Ecosystem abstract interface"
```

---

### Task 2: Create `ecosystems/` directory structure

**Files:**
- Create: `ecosystems/__init__.py`
- Create: `ecosystems/python.py`
- Create: `ecosystems/javascript.py`
- Create: `ecosystems/go.py`

**Step 1: Create ecosystems/__init__.py**

```python
from __future__ import annotations

from pathlib import Path

from base import Ecosystem


def detect_all(path: Path) -> list[Ecosystem]:
    """Scan directory, return list of detected ecosystems in priority order."""
    from ecosystems.python import PythonEcosystem
    from ecosystems.javascript import JavaScriptEcosystem
    from ecosystems.go import GoEcosystem

    all_ecosystems = [
        PythonEcosystem(),
        JavaScriptEcosystem(),
        GoEcosystem(),
    ]

    detected = []
    for eco in all_ecosystems:
        if eco.detect(path):
            detected.append(eco)

    return detected
```

**Step 2: Create ecosystems/python.py with minimal stub**

```python
from __future__ import annotations

from pathlib import Path

from base import Ecosystem, Package, DepSource, RegistryPackageInfo, EnvInfo


class PythonEcosystem(Ecosystem):
    name = "python"
    display_name = "Python"
    source_colors = {
        "pyproject.toml": "#bb9af7",
        "requirements.txt": "#7dcfff",
        "setup.py": "#e0af02",
        "setup.cfg": "#e0af02",
        "Pipfile": "#9ece6a",
        "venv": "#565f89",
    }
    source_abbrevs = {
        "pyproject.toml": "pyproj",
        "requirements.txt": "reqs",
    }

    def detect(self, path: Path) -> bool:
        files = ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"]
        return any((path / f).exists() for f in files)

    async def load_dependencies(self, path: Path) -> list[Package]:
        # TODO: move from app.py
        return []

    async def init_project(self, path: Path) -> tuple[bool, str]:
        # TODO: wrap uv init
        return False, "Not implemented"

    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        return False, "Not implemented"

    async def remove(self, package: str, source: str, group: str | None = None) -> tuple[bool, str]:
        return False, "Not implemented"

    async def sync(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def lock(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def create_env(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def validate_package(self, name: str, version: str | None = None) -> tuple[bool, str, str]:
        return False, "Not implemented", ""

    async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
        return {}

    async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
        return []

    async def fetch_package_metadata(self, name: str) -> dict[str, str]:
        return {}

    async def get_package_requires(self, name: str) -> list[str]:
        return []

    async def get_env_info(self) -> EnvInfo:
        return EnvInfo("Python", "", "uv", "", ".venv", False)

    def get_docs_url(self, name: str) -> str:
        return f"https://pypi.org/project/{name}/"
```

**Step 3: Create ecosystems/javascript.py with minimal stub**

```python
from __future__ import annotations

from pathlib import Path

from base import Ecosystem, Package, DepSource, RegistryPackageInfo, EnvInfo


class JavaScriptEcosystem(Ecosystem):
    name = "javascript"
    display_name = "JavaScript"
    source_colors = {
        "package.json": "#9ece6a",
        "package-lock.json": "#565f89",
        "node_modules": "#565f89",
    }
    source_abbrevs = {
        "package.json": "pkg.json",
    }

    def detect(self, path: Path) -> bool:
        return (path / "package.json").exists()

    async def load_dependencies(self, path: Path) -> list[Package]:
        return []

    async def init_project(self, path: Path) -> tuple[bool, str]:
        return False, "Not implemented"

    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        return False, "Not implemented"

    async def remove(self, package: str, source: str, group: str | None = None) -> tuple[bool, str]:
        return False, "Not implemented"

    async def sync(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def lock(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def create_env(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def validate_package(self, name: str, version: str | None = None) -> tuple[bool, str, str]:
        return False, "Not implemented", ""

    async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
        return {}

    async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
        return []

    async def fetch_package_metadata(self, name: str) -> dict[str, str]:
        return {}

    async def get_package_requires(self, name: str) -> list[str]:
        return []

    async def get_env_info(self) -> EnvInfo:
        return EnvInfo("Node.js", "", "npm", "", "node_modules", False)

    def get_docs_url(self, name: str) -> str:
        return f"https://www.npmjs.com/package/{name}"
```

**Step 4: Create ecosystems/go.py with minimal stub**

```python
from __future__ import annotations

from pathlib import Path

from base import Ecosystem, Package, DepSource, RegistryPackageInfo, EnvInfo


class GoEcosystem(Ecosystem):
    name = "go"
    display_name = "Go"
    source_colors = {
        "go.mod": "#7dcfff",
        "go.sum": "#565f89",
    }
    source_abbrevs = {
        "go.mod": "go.mod",
    }

    def detect(self, path: Path) -> bool:
        return (path / "go.mod").exists()

    async def load_dependencies(self, path: Path) -> list[Package]:
        return []

    async def init_project(self, path: Path) -> tuple[bool, str]:
        return False, "Not implemented"

    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        return False, "Not implemented"

    async def remove(self, package: str, source: str, group: str | None = None) -> tuple[bool, str]:
        return False, "Not implemented"

    async def sync(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def lock(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def create_env(self) -> tuple[bool, str]:
        return False, "Not implemented"

    async def validate_package(self, name: str, version: str | None = None) -> tuple[bool, str, str]:
        return False, "Not implemented", ""

    async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
        return {}

    async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
        return []

    async def fetch_package_metadata(self, name: str) -> dict[str, str]:
        return {}

    async def get_package_requires(self, name: str) -> list[str]:
        return []

    async def get_env_info(self) -> EnvInfo:
        return EnvInfo("Go", "", "go", "", "GOPATH", False)

    def get_docs_url(self, name: str) -> str:
        return f"https://pkg.go.dev/{name}"
```

**Step 5: Commit**

```bash
git add ecosystems/
git commit -m "feat: create ecosystems directory with stub implementations"
```

---

## Phase 2: Implement Python Ecosystem (Refactor Existing Code)

### Task 3: Move PackageManager to PythonEcosystem

**Files:**
- Modify: `ecosystems/python.py`

**Step 1: Copy PackageManager class from app.py to python.py**

Move the `PackageManager` class (lines 94-174 in app.py) to ecosystems/python.py.

**Step 2: Modify PythonEcosystem to use PackageManager**

```python
class PythonEcosystem(Ecosystem):
    def __init__(self):
        self._pkg_mgr = PackageManager()
    
    async def init_project(self, path: Path) -> tuple[bool, str]:
        return self._pkg_mgr.init_project()
    
    async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
        return self._pkg_mgr.add(spec, group)
    
    # etc.
```

**Step 3: Commit**

```bash
git commit -m "feat: integrate PackageManager into PythonEcosystem"
```

---

### Task 4: Move parsing functions to PythonEcosystem

**Files:**
- Modify: `ecosystems/python.py`

**Step 1: Move these functions from app.py:**
- `_DEP_RE`, `_normalise()`, `_parse_dep_string()`
- `_parse_lock()`, `_parse_pyproject()`, `_parse_requirements()`, `_parse_setup_py()`, `_parse_setup_cfg()`, `_parse_pipfile()`, `_parse_installed()`
- `_remove_from_requirements()`, `_remove_from_setup_cfg()`, `_remove_from_pipfile()`

**Step 2: Implement `load_dependencies()` method**

```python
async def load_dependencies(self, path: Path) -> list[Package]:
    """Scan for Python dependency sources and merge by normalized name."""
    all_deps: dict[str, Package] = {}

    # Parse each source file
    # Merge into all_deps by normalized name
    # Resolve versions from uv.lock

    return list(all_deps.values())
```

**Step 3: Commit**

```bash
git commit -m "feat: move Python parsing functions to PythonEcosystem"
```

---

### Task 5: Move PyPI registry to PythonEcosystem

**Files:**
- Modify: `ecosystems/python.py`

**Step 1: Move these functions from app.py:**
- `_get_pypi_json()`, `validate_pypi()`, `_fetch_latest_versions()`, `_fetch_pypi_index()`, `_search_pypi_index()`, `_fetch_pypi_metadata()`

**Step 2: Implement registry methods in PythonEcosystem**

```python
async def validate_package(self, name: str, version: str | None = None) -> tuple[bool, str, str]:
    return validate_pypi(name, version)

async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
    return await _fetch_latest_versions(names)

async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
    return await _search_pypi_index(query)

async def fetch_package_metadata(self, name: str) -> dict[str, str]:
    return await _fetch_pypi_metadata(name)

async def get_package_requires(self, name: str) -> list[str]:
    return await _get_package_requires(name)
```

**Step 3: Commit**

```bash
git commit -m "feat: move PyPI registry methods to PythonEcosystem"
```

---

### Task 6: Move environment info to PythonEcosystem

**Files:**
- Modify: `ecosystems/python.py`

**Step 1: Move these functions from app.py:**
- `_get_python_version()`, `_get_uv_version()`, `_get_app_version()`, `_venv_exists()`

**Step 2: Implement `get_env_info()`**

```python
async def get_env_info(self) -> EnvInfo:
    python_ver = _get_python_version()
    uv_ver = _get_uv_version()
    venv_exists = _venv_exists()
    
    return EnvInfo(
        language_name="Python",
        language_version=python_ver,
        tool_name="uv",
        tool_version=uv_ver,
        env_label=".venv",
        env_exists=venv_exists,
    )
```

**Step 3: Commit**

```bash
git commit -m "feat: move environment info to PythonEcosystem"
```

---

## Phase 3: Implement JavaScript Ecosystem

### Task 7: Implement JavaScript detection and parsing

**Files:**
- Modify: `ecosystems/javascript.py`

**Step 1: Implement detect()**

```python
def detect(self, path: Path) -> bool:
    return (path / "package.json").exists()
```

**Step 2: Implement package.json parser**

```python
async def _parse_package_json(self, path: Path) -> list[tuple[str, str, str]]:
    """Parse package.json dependencies. Returns [(name, specifier, group)]."""
    import json
    
    pkg_path = path / "package.json"
    if not pkg_path.exists():
        return []
    
    with open(pkg_path) as f:
        data = json.load(f)
    
    deps = []
    for group in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
        if group in data:
            for name, spec in data[group].items():
                deps.append((name, spec, group))
    
    return deps
```

**Step 3: Implement package-lock.json parser**

```python
async def _parse_package_lock(self, path: Path) -> dict[str, str]:
    """Parse package-lock.json for installed versions. Returns {name: version}."""
    # Similar structure - read packages or dependencies
    pass
```

**Step 4: Implement load_dependencies()**

```python
async def load_dependencies(self, path: Path) -> list[Package]:
    deps = await self._parse_package_json(path)
    # Merge by name, add installed versions from package-lock
    return packages
```

**Step 5: Commit**

```bash
git commit -m "feat: implement JavaScript detection and parsing"
```

---

### Task 8: Implement npm package manager wrapper

**Files:**
- Modify: `ecosystems/javascript.py`

**Step 1: Add PackageManager helper**

```python
class NpmManager:
    def __init__(self):
        self._npm = shutil.which("npm")
    
    async def _run(self, *args: str) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            self._npm, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()
    
    async def init(self, path: Path) -> tuple[bool, str]:
        code, out, err = await self._run("init", "-y")
        return code == 0, err or out
    
    async def install(self, spec: str, dev: bool = False) -> tuple[bool, str]:
        args = ["install", spec]
        if dev:
            args.insert(2, "--save-dev")
        code, out, err = await self._run(*args)
        return code == 0, err or out
    
    async def uninstall(self, pkg: str) -> tuple[bool, str]:
        code, out, err = await self._run("uninstall", pkg)
        return code == 0, err or out
    
    async def update(self, spec: str) -> tuple[bool, str]:
        code, out, err = await self._run("install", spec)
        return code == 0, err or out
    
    async def list_installed(self) -> dict[str, str]:
        code, out, err = await self._run("list", "--json", "--depth=0")
        if code != 0:
            return {}
        import json
        data = json.loads(out)
        # parse dependencies
        return {}
```

**Step 2: Wire up ecosystem methods**

```python
async def init_project(self, path: Path) -> tuple[bool, str]:
    return await self._npm.init(path)

async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
    dev = (group == "dev")
    return await self._npm.install(spec, dev=dev)

async def remove(self, package: str, source: str, group: str | None = None) -> tuple[bool, str]:
    return await self._npm.uninstall(package)

async def sync(self) -> tuple[bool, str]:
    return await self._npm.install()

async def lock(self) -> tuple[bool, str]:
    # npm generates package-lock.json automatically
    return True, "package-lock.json auto-generated"

async def create_env(self) -> tuple[bool, str]:
    # npm creates node_modules on install, no separate venv
    return True, "node_modules created on install"
```

**Step 3: Commit**

```bash
git commit -m "feat: implement npm package manager wrapper"
```

---

### Task 9: Implement npmjs.org registry

**Files:**
- Modify: `ecosystems/javascript.py`

**Step 1: Add registry helper**

```python
import requests

NPM_REGISTRY = "https://registry.npmjs.org"

async def _get_npm_json(name: str) -> dict | None:
    url = f"{NPM_REGISTRY}/{name}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None

async def _search_npm(query: str) -> list[dict]:
    url = f"{NPM_REGISTRY}/-/v1/search"
    params = {"text": query, "size": 20}
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("objects", [])
    except requests.RequestException:
        pass
    return []
```

**Step 2: Implement registry methods**

```python
async def validate_package(self, name: str, version: str | None = None) -> tuple[bool, str, str]:
    data = await _get_npm_json(name)
    if not data:
        return False, f"Package '{name}' not found on npm", ""
    
    latest = data.get("dist-tags", {}).get("latest", "")
    if version and version not in data.get("versions", {}):
        return False, f"Version {version} not found", ""
    
    return True, "", latest

async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
    results = {}
    for name in names:
        data = await _get_npm_json(name)
        if data:
            results[name] = data.get("dist-tags", {}).get("latest", "")
    return results

async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
    results = await _search_npm(query)
    return [
        RegistryPackageInfo(
            name=r.get("package", {}).get("name", ""),
            latest_version=r.get("package", {}).get("version", ""),
            description=r.get("package", {}).get("description", ""),
        )
        for r in results
    ]

async def fetch_package_metadata(self, name: str) -> dict[str, str]:
    data = await _get_npm_json(name)
    if not data:
        return {}
    
    latest = data.get("dist-tags", {}).get("latest", "")
    version_data = data.get("versions", {}).get(latest, {})
    
    return {
        "name": data.get("name", ""),
        "version": latest,
        "description": data.get("description", ""),
        "license": version_data.get("license", ""),
        "homepage": data.get("homepage", ""),
        "author": str(data.get("author", {})),
    }
```

**Step 3: Commit**

```bash
git commit -m "feat: implement npmjs.org registry integration"
```

---

### Task 10: Implement JavaScript environment info

**Files:**
- Modify: `ecosystems/javascript.py`

**Step 1: Add Node.js/npm detection**

```python
async def _get_node_version() -> str:
    proc = await asyncio.create_subprocess_exec", "--version",
        stdout=asyncio.subprocess.P(
        "nodeIPE,
    )
    out, _ = await proc.communicate()
    return out.decode().strip()

async def _get_npm_version() -> str:
    proc = await asyncio.create_subprocess_exec(
        "npm", "--version",
        stdout=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    return out.decode().strip()
```

**Step 2: Implement get_env_info()**

```python
async def get_env_info(self) -> EnvInfo:
    node_ver = await _get_node_version() or "not found"
    npm_ver = await _get_npm_version() or "not found"
    nm_exists = (Path.cwd() / "node_modules").exists()
    
    return EnvInfo(
        language_name="Node.js",
        language_version=node_ver,
        tool_name="npm",
        tool_version=npm_ver,
        env_label="node_modules",
        env_exists=nm_exists,
    )
```

**Step 3: Commit**

```bash
git commit -m "feat: implement JavaScript environment info"
```

---

## Phase 4: Implement Go Ecosystem

### Task 11: Implement Go detection and parsing

**Files:**
- Modify: `ecosystems/go.py`

**Step 1: Implement go.mod parser**

```python
async def _parse_go_mod(self, path: Path) -> list[tuple[str, str, bool]]:
    """Parse go.mod for require statements. Returns [(module, version, is_indirect)]."""
    mod_path = path / "go.mod"
    if not mod_path.exists():
        return []
    
    deps = []
    with open(mod_path) as f:
        content = f.read()
    
    # Parse require(...) blocks
    in_require = False
    for line in content.splitlines():
        line = line.strip()
        
        if line.startswith("require ("):
            in_require = True
            continue
        elif line == ")" and in_require:
            in_require = False
            continue
        
        if in_require or line.startswith("require "):
            if line.startswith("require "):
                line = line[8:].strip()
            
            # Parse "module v1.2.3" or "module v1.2.3 // indirect"
            parts = line.split()
            if len(parts) >= 2:
                module = parts[0]
                version = parts[1]
                is_indirect = "// indirect" in line
                deps.append((module, version, is_indirect))
    
    return deps
```

**Step 2: Implement load_dependencies()**

```python
async def load_dependencies(self, path: Path) -> list[Package]:
    deps = await self._parse_go_mod(path)
    # Parse go.sum for verified hashes if needed
    # Merge by module name
    return packages
```

**Step 3: Commit**

```bash
git commit -m "feat: implement Go detection and parsing"
```

---

### Task 12: Implement Go CLI wrapper

**Files:**
- Modify: `ecosystems/go.py`

**Step 1: Add Go CLI helper**

```python
class GoManager:
    def __init__(self):
        self._go = shutil.which("go")
    
    async def _run(self, *args: str) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            self._go, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()
    
    async def init(self, module_name: str) -> tuple[bool, str]:
        code, out, err = await self._run("mod", "init", module_name)
        return code == 0, err or out
    
    async def get(self, spec: str) -> tuple[bool, str]:
        # spec format: module@version
        code, out, err = await self._run("get", spec)
        return code == 0, err or out
    
    async def remove(self, module: str) -> tuple[bool, str]:
        # go get module@none removes, then go mod tidy cleans up
        code1, _, err1 = await self._run("get", f"{module}@none")
        code2, _, err2 = await self._run("mod", "tidy")
        success = code1 == 0 and code2 == 0
        return success, err1 or err2
    
    async def tidy(self) -> tuple[bool, str]:
        code, out, err = await self._run("mod", "tidy")
        return code == 0, err or out
    
    async def download(self) -> tuple[bool, str]:
        code, out, err = await self._run("mod", "download")
        return code == 0, err or out
    
    async def list_all(self) -> list[dict]:
        code, out, err = await self._run("list", "-m", "-json", "all")
        if code != 0:
            return []
        # Parse JSON lines
        modules = []
        for line in out.splitlines():
            if line.strip():
                try:
                    modules.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return modules
```

**Step 2: Wire up ecosystem methods**

```python
async def init_project(self, path: Path) -> tuple[bool, str]:
    # Extract module name from directory or prompt
    module_name = path.name
    return await self._go.init(module_name)

async def add(self, spec: str, group: str | None = None) -> tuple[bool, str]:
    return await self._go.get(spec)

async def remove(self, package: str, source: str, group: str | None = None) -> tuple[bool, str]:
    return await self._go.remove(package)

async def sync(self) -> tuple[bool, str]:
    return await self._go.tidy()

async def lock(self) -> tuple[bool, str]:
    return await self._go.download()

async def create_env(self) -> tuple[bool, str]:
    # Go doesn't have venvs - modules are global
    return True, "Go modules don't require environment creation"
```

**Step 3: Commit**

```bash
git commit -m "feat: implement Go CLI wrapper"
```

---

### Task 13: Implement Go registry (proxy.golang.org)

**Files:**
- Modify: `ecosystems/go.py`

**Step 1: Add registry helpers**

```python
GO_PROXY = "https://proxy.golang.org"

async def _get_go_module_info(module: str) -> dict | None:
    url = f"{GO_PROXY}/{module}/@latest"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None

async def _list_go_versions(module: str) -> list[str]:
    url = f"{GO_PROXY}/{module}/@v/list"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.text.strip().splitlines()
    except requests.RequestException:
        pass
    return []
```

**Step 2: Implement registry methods**

```python
async def validate_package(self, name: str, version: str | None = None) -> tuple[bool, str, str]:
    data = await _get_go_module_info(name)
    if not data:
        return False, f"Module '{name}' not found on proxy.golang.org", ""
    
    latest = data.get("Version", "")
    if version and version != latest:
        versions = await _list_go_versions(name)
        if version not in versions:
            return False, f"Version {version} not found", ""
    
    return True, "", latest

async def fetch_latest_versions(self, names: list[str]) -> dict[str, str]:
    results = {}
    for name in names:
        data = await _get_go_module_info(name)
        if data:
            results[name] = data.get("Version", "")
    return results

async def search_registry(self, query: str) -> list[RegistryPackageInfo]:
    # Go doesn't have a good search API, use pkg.go.dev scrape
    # For now, return empty - requires HTML scraping
    return []

async def fetch_package_metadata(self, name: str) -> dict[str, str]:
    data = await _get_go_module_info(name)
    if not data:
        return {}
    
    return {
        "name": data.get("Name", ""),
        "version": data.get("Version", ""),
        "description": data.get("Summary", ""),
        "license": data.get("License", ""),
        "homepage": data.get("Homepage", ""),
    }
```

**Step 3: Commit**

```bash
git commit -m "feat: implement Go registry integration"
```

---

### Task 14: Implement Go environment info

**Files:**
- Modify: `ecosystems/go.py`

**Step 1: Add Go version detection**

```python
async def _get_go_version() -> str:
    proc = await asyncio.create_subprocess_exec(
        "go", "version",
        stdout=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    # Output: "go version go1.22.1 linux/amd64"
    match = re.search(r"go(\d+\.\d+\.\d+)", out.decode())
    return match.group(1) if match else ""
```

**Step 2: Implement get_env_info()**

```python
async def get_env_info(self) -> EnvInfo:
    go_ver = await _get_go_version() or "not found"
    
    return EnvInfo(
        language_name="Go",
        language_version=go_ver,
        tool_name="go",
        tool_version=go_ver,
        env_label="GOPATH",
        env_exists=True,  # Go modules don't need explicit env
    )
```

**Step 3: Commit**

```bash
git commit -m "feat: implement Go environment info"
```

---

## Phase 5: Integrate with TUI (app.py)

### Task 15: Refactor app.py to use ecosystems

**Files:**
- Modify: `app.py`

**Step 1: Import ecosystems**

```python
from ecosystems import detect_all
from ecosystems.python import PythonEcosystem
```

**Step 2: Modify __init__**

```python
class DependencyManagerApp(App):
    def __init__(self):
        self._ecosystems: list[Ecosystem] = []
        self._active_ecosystem: Ecosystem | None = None
        self._packages: list[Package] = []
        # Remove old Python-specific init
```

**Step 3: Modify on_mount**

```python
def on_mount(self):
    # Detect ecosystems
    self._ecosystems = detect_all(Path.cwd())
    
    if self._ecosystems:
        self._active_ecosystem = self._ecosystems[0]
        # Load packages
    else:
        # Show init prompt
```

**Step 4: Modify all methods to use active ecosystem**

- Replace `_refresh_data()` to call `active_eco.load_dependencies()`
- Replace `action_add_package()` to call `active_eco.add()`
- Replace `action_delete_package()` to call `active_eco.remove()`
- Replace `action_sync()` to call `active_eco.sync()`
- Replace `action_lock()` to call `active_eco.lock()`
- Replace `action_init_project()` to call `active_eco.init_project()`
- Replace `action_create_venv()` to call `active_eco.create_env()`
- Replace `_check_all_outdated()` to use `active_eco.fetch_latest_versions()`
- Replace registry calls to use `active_eco` methods
- Update status panel to show `active_eco.get_env_info()`

**Step 5: Commit**

```bash
git commit -m "feat: refactor app.py to use ecosystem adapter"
```

---

### Task 16: Add ecosystem switching keybindings

**Files:**
- Modify: `app.py`

**Step 1: Add ecosystem cycling method**

```python
def _cycle_ecosystem(self, forward: bool = True):
    if not self._ecosystems or len(self._ecosystems) <= 1:
        return
    
    current_idx = self._ecosystems.index(self._active_ecosystem)
    if forward:
        next_idx = (current_idx + 1) % len(self._ecosystems)
    else:
        next_idx = (current_idx - 1) % len(self._ecosystems)
    
    self._active_ecosystem = self._ecosystems[next_idx]
    # Reload packages
    self._refresh_data()
```

**Step 2: Add keybinding**

```python
def on_key(self, event: events.Key):
    if event.key == "e":
        self._cycle_ecosystem(forward=True)
    elif event.key == "E":
        self._cycle_ecosystem(forward=False)
```

**Step 3: Update title to show active ecosystem**

```python
@property
def SUB_TITLE(self) -> str:
    if self._active_ecosystem:
        return f"{self._active_ecosystem.display_name} Dependency Manager"
    return "No project detected"
```

**Step 4: Commit**

```bash
git commit -m "feat: add ecosystem switching with e/E keys"
```

---

## Phase 6: Testing

### Task 17: Create test_ecosystems.py

**Files:**
- Create: `test_ecosystems.py`

**Step 1: Create test file with ecosystem tests**

```python
import pytest
from pathlib import Path
import json
import tempfile

# Test PythonEcosystem detection
def test_python_detect_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
    eco = PythonEcosystem()
    assert eco.detect(tmp_path) == True

def test_python_detect_no_files(tmp_path):
    eco = PythonEcosystem()
    assert eco.detect(tmp_path) == False

# Test JavaScriptEcosystem detection
def test_js_detect_package_json(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "test"}')
    eco = JavaScriptEcosystem()
    assert eco.detect(tmp_path) == True

# Test GoEcosystem detection
def test_go_detect_go_mod(tmp_path):
    (tmp_path / "go.mod").write_text("module test\ngo 1.21")
    eco = GoEcosystem()
    assert eco.detect(tmp_path) == True
```

**Step 2: Run tests**

```bash
uv run pytest test_ecosystems.py -v
```

**Step 3: Commit**

```bash
git add test_ecosystems.py
git commit -m "test: add ecosystem unit tests"
```

---

### Task 18: Add TUI integration tests

**Files:**
- Modify: `test_app.py`

**Step 1: Add ecosystem switching tests**

```python
@pytest.mark.asyncio
async def test_press_e_cycles_ecosystems(app_multi_lang):
    async with app_multi_lang.run_test() as pilot:
        # Should start on Python
        assert "Python" in app_multi_lang.SUB_TITLE
        
        await pilot.press("e")
        await pilot.pause()
        
        # Should switch to JavaScript
        assert "JavaScript" in app_multi_lang.SUB_TITLE
        
        await pilot.press("e")
        await pilot.pause()
        
        # Should switch to Go
        assert "Go" in app_multi_lang.SUB_TITLE
```

**Step 2: Run tests**

```bash
uv run pytest test_app.py -v -k "ecosystem"
```

**Step 3: Commit**

```bash
git commit -m "test: add ecosystem switching TUI tests"
```

---

## Phase 7: Final Integration

### Task 19: Run full test suite

**Files:**
- Run all tests

**Step 1: Run full test suite**

```bash
uv run pytest test_app.py test_ecosystems.py -v
```

**Step 2: Fix any failures**

**Step 3: Run linter**

```bash
uv run ruff check app.py base.py ecosystems/
```

**Step 4: Format**

```bash
uv run ruff format app.py base.py ecosystems/
```

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete multi-language support implementation"
```

---

## Plan Complete

This implementation plan has 19 tasks across 7 phases. Each task is designed to be completed in 2-5 minutes with a commit after each step.

**Plan complete and saved to `docs/plans/2026-02-22-multi-language-support-design.md`.**

Two execution options:

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
