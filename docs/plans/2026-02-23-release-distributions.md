# Release Distribution Packages Implementation Plan

> **For Claude:** REQUIRED SUB-Skill: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Create native distribution packages (.deb, .rpm, .pkg.tar.zst) and GitHub release automation for PyDep.

**Architecture:** Pre-built PyInstaller binary packaged as native distro packages. Each package contains the standalone binary + metadata. GitHub Actions automates release creation with all artifacts.

**Tech Stack:** dpkg-deb, rpmbuild, makepkg, GitHub Actions

---

## Task 1: Create Debian Package Build

**Files:**
- Create: `/home/eslam/coding/projects/pydep/scripts/build-deb.sh`
- Create: `/home/eslam/coding/projects/pydep/packaging/debian/DEBIAN/control`

**Step 1: Create build directory structure**

Run:
```bash
mkdir -p /home/eslam/coding/projects/pydep/packaging/debian/usr/bin
mkdir -p /home/eslam/coding/projects/pydep/packaging/debian/DEBIAN
```

**Step 2: Copy binary**

Run:
```bash
cp /home/eslam/coding/projects/pydep/dist/pydep /home/eslam/coding/projects/pydep/packaging/debian/usr/bin/pydep
chmod +x /home/eslam/coding/projects/pydep/packaging/debian/usr/bin/pydep
```

**Step 3: Create DEBIAN/control file**

File: `/home/eslam/coding/projects/pydep/packaging/debian/DEBIAN/control`
```
Package: pydep
Version: 0.1.0
Section: utils
Priority: optional
Architecture: amd64
Depends: bash (>= 4.0)
Maintainer: Your Name <your@email.com>
Description: Multi-language dependency manager TUI
 A fully keyboard-driven terminal UI for managing
 Python, JavaScript, and Go dependencies.
```

**Step 4: Create build script**

File: `/home/eslam/coding/projects/pydep/scripts/build-deb.sh`:
```bash
#!/bin/bash
set -e

VERSION="0.1.0"
ARCH="amd64"
DIST_DIR="/home/eslam/coding/projects/pydep/packaging/debian"
OUTPUT_DIR="/home/eslam/coding/projects/pydep/dist"

mkdir -p "$OUTPUT_DIR"

# Build package
dpkg-deb --build "$DIST_DIR" "$OUTPUT_DIR/pydep_${VERSION}_${ARCH}.deb"

echo "Created: $OUTPUT_DIR/pydep_${VERSION}_${ARCH}.deb"
```

Run: `chmod +x /home/eslam/coding/projects/pydep/scripts/build-deb.sh`

**Step 5: Build the package**

Run: `/home/eslam/coding/projects/pydep/scripts/build-deb.sh`

Verify: `ls -la /home/eslam/coding/projects/pydep/dist/*.deb`

**Step 6: Commit**

```bash
git add scripts/build-deb.sh packaging/debian/
git commit -m "feat: add Debian package build"
```

---

## Task 2: Create Fedora/RPM Package

**Files:**
- Create: `/home/eslam/coding/projects/pydep/packaging/fedora/pydep.spec`
- Create: `/home/eslam/coding/projects/pydep/scripts/build-rpm.sh`

**Step 1: Create RPM build structure**

Run:
```bash
mkdir -p ~/rpmbuild/SPECS ~/rpmbuild/SOURCES ~/rpmbuild/BUILD
mkdir -p /home/eslam/coding/projects/pydep/packaging/fedora
```

**Step 2: Create spec file**

File: `/home/eslam/coding/projects/pydep/packaging/fedora/pydep.spec`
```
Name:           pydep
Version:        0.1.0
Release:        1%{?dist}
Summary:        Multi-language dependency manager TUI
License:        MIT
URL:            https://github.com/EslamMohamed365/pydep
BuildArch:      x86_64

%description
A fully keyboard-driven terminal UI for managing
Python, JavaScript, and Go dependencies.

%install
mkdir -p %{buildroot}/usr/bin
install -m 755 %{_sourcedir}/pydep %{buildroot}/usr/bin/pydep

%files
/usr/bin/pydep

%changelog
* Mon Feb 23 2026 Your Name <your@email.com> - 0.1.0-1
- Initial package
```

**Step 3: Copy binary to sources**

Run:
```bash
cp /home/eslam/coding/projects/pydep/dist/pydep ~/rpmbuild/SOURCES/pydep
```

**Step 4: Create build script**

File: `/home/eslam/coding/projects/pydep/scripts/build-rpm.sh`:
```bash
#!/bin/bash
set -e

VERSION="0.1.0"
OUTPUT_DIR="/home/eslam/coding/projects/pydep/dist"

# Setup RPM build root if needed
if [ ! -d ~/rpmbuild ]; then
    rpmdev-setuptree
fi

# Copy spec and source
cp /home/eslam/coding/projects/pydep/packaging/fedora/pydep.spec ~/rpmbuild/SPECS/
cp /home/eslam/coding/projects/pydep/dist/pydep ~/rpmbuild/SOURCES/

# Build RPM
rpmbuild -bb ~/rpmbuild/SPECS/pydep.spec

# Copy to dist
mkdir -p "$OUTPUT_DIR"
cp ~/rpmbuild/RPMS/x86_64/pydep-*.rpm "$OUTPUT_DIR/"

echo "Created: $OUTPUT_DIR/pydep-${VERSION}-1.x86_64.rpm"
```

Run: `chmod +x /home/eslam/coding/projects/pydep/scripts/build-rpm.sh`

**Step 5: Build the package**

Run: `/home/eslam/coding/projects/pydep/scripts/build-rpm.sh`

Verify: `ls -la /home/eslam/coding/projects/pydep/dist/*.rpm`

**Step 6: Commit**

```bash
git add scripts/build-rpm.sh packaging/fedora/
git commit -m "feat: add Fedora/RPM package build"
```

---

## Task 3: Create Arch Linux PKGBUILD

**Files:**
- Create: `/home/eslam/coding/projects/pydep/packaging/arch/PKGBUILD`
- Create: `/home/eslam/coding/projects/pydep/scripts/build-arch.sh`

**Step 1: Create arch packaging directory**

Run:
```bash
mkdir -p /home/eslam/coding/projects/pydep/packaging/arch
```

**Step 2: Create PKGBUILD**

File: `/home/eslam/coding/projects/pydep/packaging/arch/PKGBUILD`:
```bash
# Maintainer: Your Name <your@email.com>
pkgname=pydep
pkgver=0.1.0
pkgrel=1
pkgdesc="Multi-language dependency manager TUI"
arch=('x86_64')
url="https://github.com/EslamMohamed365/pydep"
license=('MIT')
depends=('bash')
source=("pydep::file://$HOME/path/to/pydep/dist/pydep")
sha256sums=('SKIP')

package() {
  install -Dm755 "$srcdir/pydep" "$pkgdir/usr/bin/pydep"
}
```

**Step 3: Create build script**

File: `/home/eslam/coding/projects/pydep/scripts/build-arch.sh`:
```bash
#!/bin/bash
set -e

VERSION="0.1.0"
PKG_DIR="/home/eslam/coding/projects/pydep/packaging/arch"
OUTPUT_DIR="/home/eslam/coding/projects/pydep/dist"

mkdir -p "$OUTPUT_DIR"

# Build package (on Arch Linux)
cd "$PKG_DIR"
makepkg --noconfirm --nodeps

# Copy result
cp *.pkg.tar.zst "$OUTPUT_DIR/"

echo "Created: $OUTPUT_DIR/pydep-${VERSION}-1-x86_64.pkg.tar.zst"
```

Run: `chmod +x /home/eslam/coding/projects/pydep/scripts/build-arch.sh`

**Step 4: Commit**

```bash
git add scripts/build-arch.sh packaging/arch/
git commit -m "feat: add Arch Linux PKGBUILD"
```

---

## Task 4: Update README with Distribution Installation

**Files:**
- Modify: `/home/eslam/coding/projects/pydep/README.md`

**Step 1: Add Debian/Ubuntu section after Installation**

Add after "## Installation":

```markdown
### Debian/Ubuntu

```bash
# Download release
curl -L -o pydep_0.1.0_amd64.deb https://github.com/EslamMohamed365/pydep/releases/download/v0.1.0/pydep_0.1.0_amd64.deb

# Install
sudo dpkg -i pydep_0.1.0_amd64.deb

# Or with gdebi (auto-installs dependencies)
sudo gdebi pydep_0.1.0_amd64.deb
```

### Fedora

```bash
# Download release
curl -L -o pydep-0.1.0-1.x86_64.rpm https://github.com/EslamMohamed365/pydep/releases/download/v0.1.0/pydep-0.1.0-1.x86_64.rpm

# Install
sudo dnf install pydep-0.1.0-1.x86_64.rpm
```

### Arch Linux

```bash
# Install from AUR (recommended)
yay -S pydep

# Or manual build
curl -L -o pydep.tar.zst https://github.com/EslamMohamed365/pydep/releases/download/v0.1.0/pydep-0.1.0-1-x86_64.pkg.tar.zst
sudo pacman -U pydep.tar.zst
```
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add distribution installation instructions"
```

---

## Task 5: Create GitHub Actions Release Workflow

**Files:**
- Create: `/home/eslam/coding/projects/pydep/.github/workflows/release.yml`

**Step 1: Create workflow file**

File: `/home/eslam/coding/projects/pydep/.github/workflows/release.yml`:
```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install pyinstaller>=6.0 requests textual

      - name: Build executable
        run: |
          pyinstaller pyinstaller.spec --noconfirm
          ls -la dist/

      - name: Build Debian package
        run: |
          mkdir -p packaging/debian/usr/bin
          cp dist/pydep packaging/debian/usr/bin/
          chmod +x packaging/debian/usr/bin/pydep
          dpkg-deb --build packaging/debian dist/pydep_${{ github.ref_name }}_amd64.deb

      - name: Build RPM package
        run: |
          pip install rpm
          mkdir -p ~/rpmbuild/SPECS ~/rpmbuild/SOURCES
          cp packaging/fedora/pydep.spec ~/rpmbuild/SPECS/
          cp dist/pydep ~/rpmbuild/SOURCES/
          rpmbuild -bb ~/rpmbuild/SPECS/pydep.spec
          cp ~/rpmbuild/RPMS/x86_64/pydep-*.rpm dist/

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: |
            dist/pydep
            dist/*.deb
            dist/*.rpm
          generate_release_notes: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Step 2: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add GitHub release workflow"
```

---

## Summary

After completing all tasks:

| File | Purpose |
|------|---------|
| `dist/pydep` | Standalone executable |
| `dist/pydep_0.1.0_amd64.deb` | Debian package |
| `dist/pydep-0.1.0-1.x86_64.rpm` | Fedora package |
| `dist/pydep-0.1.0-1-x86_64.pkg.tar.zst` | Arch package |

To release:
```bash
git tag v0.1.0
git push origin v0.1.0
```

The GitHub Actions workflow will automatically build and create the release.
