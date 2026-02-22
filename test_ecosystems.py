"""Tests for ecosystem implementations."""

from __future__ import annotations

import pytest
from pathlib import Path

from base import Ecosystem
from ecosystems import detect_all
from ecosystems.python import PythonEcosystem
from ecosystems.javascript import JavaScriptEcosystem
from ecosystems.go import GoEcosystem


class TestEcosystemDetection:
    """Test ecosystem detection."""

    def test_python_detect_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        eco = PythonEcosystem()
        assert eco.detect(tmp_path) is True

    def test_python_detect_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests>=2.0")
        eco = PythonEcosystem()
        assert eco.detect(tmp_path) is True

    def test_python_detect_no_files(self, tmp_path):
        eco = PythonEcosystem()
        assert eco.detect(tmp_path) is False

    def test_js_detect_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        eco = JavaScriptEcosystem()
        assert eco.detect(tmp_path) is True

    def test_js_detect_no_package_json(self, tmp_path):
        eco = JavaScriptEcosystem()
        assert eco.detect(tmp_path) is False

    def test_go_detect_go_mod(self, tmp_path):
        (tmp_path / "go.mod").write_text("module test\ngo 1.21")
        eco = GoEcosystem()
        assert eco.detect(tmp_path) is True

    def test_go_detect_no_go_mod(self, tmp_path):
        eco = GoEcosystem()
        assert eco.detect(tmp_path) is False


class TestDetectAll:
    """Test detect_all function."""

    def test_detect_all_python_only(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        ecosystems = detect_all(tmp_path)
        assert len(ecosystems) == 1
        assert ecosystems[0].name == "python"

    def test_detect_all_js_only(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        ecosystems = detect_all(tmp_path)
        assert len(ecosystems) == 1
        assert ecosystems[0].name == "javascript"

    def test_detect_all_go_only(self, tmp_path):
        (tmp_path / "go.mod").write_text("module test\ngo 1.21")
        ecosystems = detect_all(tmp_path)
        assert len(ecosystems) == 1
        assert ecosystems[0].name == "go"

    def test_detect_all_multi(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "go.mod").write_text("module test\ngo 1.21")
        ecosystems = detect_all(tmp_path)
        assert len(ecosystems) == 3

    def test_detect_all_none(self, tmp_path):
        ecosystems = detect_all(tmp_path)
        assert len(ecosystems) == 0


class TestPythonEcosystemProperties:
    """Test PythonEcosystem properties."""

    def test_name(self):
        eco = PythonEcosystem()
        assert eco.name == "python"
        assert eco.display_name == "Python"

    def test_source_colors(self):
        eco = PythonEcosystem()
        assert "pyproject.toml" in eco.source_colors
        assert "requirements.txt" in eco.source_colors


class TestJavaScriptEcosystemProperties:
    """Test JavaScriptEcosystem properties."""

    def test_name(self):
        eco = JavaScriptEcosystem()
        assert eco.name == "javascript"
        assert eco.display_name == "JavaScript"

    def test_source_colors(self):
        eco = JavaScriptEcosystem()
        assert "package.json" in eco.source_colors


class TestGoEcosystemProperties:
    """Test GoEcosystem properties."""

    def test_name(self):
        eco = GoEcosystem()
        assert eco.name == "go"
        assert eco.display_name == "Go"

    def test_source_colors(self):
        eco = GoEcosystem()
        assert "go.mod" in eco.source_colors
