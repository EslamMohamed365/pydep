# Arch Linux Installation

## Quick Install (AUR)

```bash
# Using yay
yay -S pydep

# Or using paru
paru -S pydep
```

## Manual Build

```bash
# Clone the repository
git clone https://github.com/EslamMohamed365/pydep.git
cd pydep/packaging/arch

# Build and install
makepkg -si
```

## Verify Installation

```bash
pydep --help
```
