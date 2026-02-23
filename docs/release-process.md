# Release Process

## Prerequisites

```bash
# Install build tools
# Debian/Ubuntu
sudo apt install dpkg-dev build-essential

# Fedora
sudo dnf install rpm-build rpmdevtools

# Arch
sudo pacman -S base-devel
```

## Build All Packages

```bash
# Run QA checks first
./scripts/qa-release.sh

# Build all packages
./scripts/build-deb.sh      # Creates .deb
./scripts/build-rpm.sh      # Creates .rpm (requires Fedora)
./scripts/build-arch.sh     # Creates .pkg.tar.zst (requires Arch)
```

## Create GitHub Release

```bash
# Tag a version
git tag v0.1.0

# Push tag to trigger GitHub Actions
git push origin v0.1.0
```

The workflow will:
1. Build the executable
2. Create all packages
3. Create GitHub Release with artifacts

## Verify Release

Check the release at: https://github.com/EslamMohamed365/pydep/releases
