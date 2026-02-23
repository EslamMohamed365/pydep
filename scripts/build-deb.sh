#!/bin/bash
set -e

VERSION="0.1.0"
ARCH="amd64"
DIST_DIR="/home/eslam/coding/projects/pydep/packaging/debian"
OUTPUT_DIR="/home/eslam/coding/projects/pydep/dist"
OUTPUT_FILE="$OUTPUT_DIR/pydep_${VERSION}_${ARCH}.deb"

mkdir -p "$OUTPUT_DIR"

# Build package using Python (handles systems without dpkg-deb)
python3 - "$DIST_DIR" "$OUTPUT_FILE" << 'PYEOF'
import tarfile
import os
import io
import sys

dist_dir = sys.argv[1]
deb_path = sys.argv[2]

# Create control.tar.gz
control_tar = io.BytesIO()
with tarfile.open(fileobj=control_tar, mode="w:gz") as tar:
    # Add control file
    control_path = os.path.join(dist_dir, "DEBIAN", "control")
    tar.add(control_path, arcname="control")
    # Add maintainer scripts if they exist
    for script in ["preinst", "postinst", "prerm", "postrm"]:
        script_path = os.path.join(dist_dir, "DEBIAN", script)
        if os.path.exists(script_path):
            tar.add(script_path, arcname=script)
control_tar.seek(0)
control_data = control_tar.read()

# Create data.tar.gz
data_tar = io.BytesIO()
with tarfile.open(fileobj=data_tar, mode="w:gz") as tar:
    # Add usr directory
    usr_dir = os.path.join(dist_dir, "usr")
    for root, dirs, files in os.walk(usr_dir):
        for f in files:
            full_path = os.path.join(root, f)
            arcname = os.path.relpath(full_path, dist_dir)
            tar.add(full_path, arcname=arcname)
data_tar.seek(0)
data_data = data_tar.read()

# Create final .deb (ar archive)
with open(deb_path, "wb") as f:
    # ar magic
    f.write(b"!<arch>\n")
    
    def write_ar_member(name, data):
        # Pad name to 16 chars (convert bytes to string for padding)
        if isinstance(name, bytes):
            name = name.decode()
        name = name[:16].ljust(16)
        # timestamp, uid, gid, mode, size
        header = (name + "0     0     0     100644 " + str(len(data)) + "\n").encode()
        f.write(header)
        # Pad to even length
        if len(data) % 2:
            data += b"\n"
        f.write(data)
        if len(data) % 2 == 0:
            f.write(b"\n")
    
    # debian-binary
    write_ar_member(b"debian-binary", b"2.0\n")
    write_ar_member(b"control.tar.gz", control_data)
    write_ar_member(b"data.tar.gz", data_data)

print(f"Created: {deb_path}")
PYEOF
