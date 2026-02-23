#!/bin/bash
set -e

VERSION="0.1.0"
PKG_DIR="/home/eslam/coding/projects/pydep/packaging/arch"
OUTPUT_DIR="/home/eslam/coding/projects/pydep/dist"

mkdir -p "$OUTPUT_DIR"

# Try makepkg first (Arch Linux only)
if command -v makepkg &> /dev/null; then
    cd "$PKG_DIR"
    makepkg --noconfirm --nodeps
    cp *.pkg.tar.zst "$OUTPUT_DIR/"
else
    # Create placeholder for non-Arch systems
    echo "makepkg not available (Arch Linux only)"
    echo "On Arch Linux, run: cd $PKG_DIR && makepkg -si"
fi
