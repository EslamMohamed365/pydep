# Fedora/RHEL Installation

## Quick Install

```bash
# Download the RPM package
curl -L -o pydep-0.1.0-1.x86_64.rpm https://github.com/EslamMohamed365/pydep/releases/download/v0.1.0/pydep-0.1.0-1.x86_64.rpm

# Install with DNF
sudo dnf install pydep-0.1.0-1.x86_64.rpm
```

## Build from Source

```bash
# Install build dependencies
sudo dnf install rpm-build rpmdevtools

# Setup RPM build tree
rpmdev-setuptree

# Build the package
./scripts/build-rpm.sh
```

## Verify Installation

```bash
pydep --help
```
