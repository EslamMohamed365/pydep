# Standalone Binary Usage

## Download

Get the latest release from GitHub:
```bash
curl -L -o pydep https://github.com/EslamMohamed365/pydep/releases/latest/download/pydep
chmod +x pydep
```

## Run

```bash
./pydep
```

## Requirements

- Linux (x86_64)
- `uv` command in PATH (for package management)

## Troubleshooting

| Error | Fix |
|-------|-----|
| `uv: command not found` | Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` |
| Permission denied | `chmod +x pydep` |
