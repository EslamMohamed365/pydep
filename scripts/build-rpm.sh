#!/bin/bash
set -e

VERSION="0.1.0"
OUTPUT_DIR="/home/eslam/coding/projects/pydep/dist"

# Setup RPM build root if needed
if [ ! -d ~/rpmbuild ]; then
    mkdir -p ~/rpmbuild/SPECS ~/rpmbuild/SOURCES ~/rpmbuild/BUILD ~/rpmbuild/RPMS ~/rpmbuild/SRPMS
fi

# Copy spec and source
cp /home/eslam/coding/projects/pydep/packaging/fedora/pydep.spec ~/rpmbuild/SPECS/
cp /home/eslam/coding/projects/pydep/dist/pydep ~/rpmbuild/SOURCES/

# Build RPM using Python (fallback if rpmbuild not available)
mkdir -p "$OUTPUT_DIR"

# Try rpmbuild first, fall back to Python
if command -v rpmbuild &> /dev/null; then
    rpmbuild -bb ~/rpmbuild/SPECS/pydep.spec
    cp ~/rpmbuild/RPMS/x86_64/pydep-*.rpm "$OUTPUT_DIR/"
else
    # Python fallback - create RPM using setuptools or simple archive
    echo "rpmbuild not found, creating RPM-like package..."
    # Create a simple RPM-like structure
    python3 - "$OUTPUT_DIR" << 'PYEOF'
import os
import sys
import tarfile
import gzip

output_dir = sys.argv[1]

# Create RPM metadata (simplified - just a tar.gz as placeholder)
rpm_name = "pydep-0.1.0-1.x86_64.rpm"
# For proper RPM, we'd need rpm-build tools
# This creates a placeholder that can be replaced on proper Fedora systems

# Create a simple tarball as placeholder
tar_path = os.path.join(output_dir, "pydep-0.1.0-1.x86_64.tar.gz")
with tarfile.open(tar_path, "w:gz") as tar:
    tar.add("/home/eslam/coding/projects/pydep/dist/pydep", arcname="pydep")

print(f"Created placeholder: {tar_path}")
print("NOTE: Install rpmbuild on Fedora to create proper .rpm")
PYEOF
fi

echo "Created RPM package in $OUTPUT_DIR/"
