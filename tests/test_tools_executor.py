"""Tests for the tool executor."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 - used at runtime in fixtures

import pytest

from project_magi.tools.executor import TOOL_DEFINITIONS, ToolExecutor


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """Create a temp directory with some files."""
    (tmp_path / "hello.txt").write_text("Hello, world!\nSecond line\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "code.py").write_text("def foo():\n    return 42\n")
    return tmp_path


@pytest.fixture
def executor(tmp_root: Path) -> ToolExecutor:
    return ToolExecutor(tmp_root)


class TestToolDefinitions:
    def test_has_three_tools(self):
        assert len(TOOL_DEFINITIONS) == 3

    def test_tool_names(self):
        names = {t["name"] for t in TOOL_DEFINITIONS}
        assert names == {"read_file", "grep_content", "glob_files"}


class TestReadFile:
    def test_reads_file(self, executor: ToolExecutor, tmp_root: Path):
        result = executor.execute("read_file", {"path": "hello.txt"})
        assert "Hello, world!" in result

    def test_not_a_file(self, executor: ToolExecutor):
        result = executor.execute("read_file", {"path": "nonexistent.txt"})
        assert "Error" in result

    def test_path_escape(self, executor: ToolExecutor):
        result = executor.execute("read_file", {"path": "../../etc/passwd"})
        assert "Error" in result

    def test_truncates_large_file(self, executor: ToolExecutor, tmp_root: Path):
        (tmp_root / "big.txt").write_text("x" * 60000)
        result = executor.execute("read_file", {"path": "big.txt"})
        assert "truncated" in result


class TestGrepContent:
    def test_finds_pattern(self, executor: ToolExecutor):
        result = executor.execute("grep_content", {"pattern": "Hello"})
        assert "hello.txt:1:" in result

    def test_no_matches(self, executor: ToolExecutor):
        result = executor.execute("grep_content", {"pattern": "zzzzz"})
        assert "No matches" in result

    def test_with_glob(self, executor: ToolExecutor):
        result = executor.execute("grep_content", {"pattern": "def", "glob": "*.py"})
        assert "code.py" in result

    def test_with_path(self, executor: ToolExecutor):
        result = executor.execute("grep_content", {"pattern": "return", "path": "sub"})
        assert "code.py" in result


class TestGlobFiles:
    def test_glob_txt(self, executor: ToolExecutor):
        result = executor.execute("glob_files", {"pattern": "*.txt"})
        assert "hello.txt" in result

    def test_glob_recursive(self, executor: ToolExecutor):
        result = executor.execute("glob_files", {"pattern": "**/*.py"})
        assert "code.py" in result

    def test_no_matches(self, executor: ToolExecutor):
        result = executor.execute("glob_files", {"pattern": "*.rs"})
        assert "No files" in result


class TestUnknownTool:
    def test_unknown_tool(self, executor: ToolExecutor):
        result = executor.execute("unknown", {})
        assert "Error" in result
