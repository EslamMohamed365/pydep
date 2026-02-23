# Debian/Ubuntu Installation

## Quick Install

```bash
# Download the .deb package
curl -L -o pydep_0.1.0_amd64.deb https://github.com/EslamMohamed365/pydep/releases/download/v0.1.0/pydep_0.1.0_amd64.deb

# Install with dpkg
sudo dpkg -i pydep_0.1.0_amd64.deb

# Or install with gdebi (auto-installs dependencies)
sudo gdebi pydep_0.1.0_amd64.deb
```

## Build from Source

```bash
# Install build dependencies
sudo apt install dpkg-dev build-essential

# Build the package
./scripts/build-deb.sh
```

## Verify Installation

```bash
pydep --help
```
