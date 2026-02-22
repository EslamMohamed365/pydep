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
