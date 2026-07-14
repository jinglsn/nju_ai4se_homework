import pytest
from src.tools.registry import ToolRegistry, ToolResult
from src.tools.file_tools import read_file, write_file, edit_file
from src.tools.search_tools import grep, list_dir
from src.tools.shell_tools import run_shell


class TestToolRegistry:
    def test_register_and_list(self):
        registry = ToolRegistry()
        registry.register("read_file", lambda path: ToolResult(success=True, output=f"read {path}"), {"path": "str"})
        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "read_file"

    def test_execute_success(self):
        registry = ToolRegistry()
        registry.register("echo", lambda msg: ToolResult(success=True, output=msg), {"msg": "str"})
        result = registry.execute("echo", {"msg": "hello"})
        assert result.success is True
        assert result.output == "hello"

    def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.execute("nonexistent", {})
        assert result.success is False
        assert "unknown" in (result.error or "").lower()

    def test_execute_missing_arg(self):
        registry = ToolRegistry()
        registry.register("greet", lambda name: ToolResult(success=True, output=f"hi {name}"), {"name": "str"})
        result = registry.execute("greet", {})
        assert result.success is False

    def test_tool_count(self):
        registry = ToolRegistry()
        assert registry.tool_count == 0
        registry.register("t1", lambda: ToolResult(success=True, output=""), {})
        registry.register("t2", lambda: ToolResult(success=True, output=""), {})
        assert registry.tool_count == 2


class TestFileTools:
    def test_read_file(self, temp_workspace):
        test_file = temp_workspace / "test.txt"
        test_file.write_text("line1\nline2\nline3")
        result = read_file(str(test_file))
        assert result.success is True
        assert "line1" in result.output

    def test_read_file_line_range(self, temp_workspace):
        test_file = temp_workspace / "test.txt"
        test_file.write_text("line1\nline2\nline3\nline4")
        result = read_file(str(test_file), start_line=2, end_line=3)
        assert "line2" in result.output
        assert "line1" not in result.output

    def test_read_file_not_found(self, temp_workspace):
        result = read_file(str(temp_workspace / "nonexistent.txt"))
        assert result.success is False

    def test_write_file(self, temp_workspace):
        path = str(temp_workspace / "new.txt")
        result = write_file(path, "hello world")
        assert result.success is True
        assert (temp_workspace / "new.txt").read_text() == "hello world"

    def test_edit_file(self, temp_workspace):
        test_file = temp_workspace / "code.py"
        test_file.write_text("x = 1 + 2")
        result = edit_file(str(test_file), "1 + 2", "2 + 3")
        assert result.success is True
        assert test_file.read_text() == "x = 2 + 3"

    def test_edit_file_replace_all(self, temp_workspace):
        test_file = temp_workspace / "code.py"
        test_file.write_text("x = a + b\ny = a + b")
        result = edit_file(str(test_file), "a + b", "c + d", replace_all=True)
        assert result.success is True
        assert test_file.read_text() == "x = c + d\ny = c + d"

    def test_edit_file_not_found(self, temp_workspace):
        test_file = temp_workspace / "code.py"
        test_file.write_text("x = 1 + 2")
        result = edit_file(str(test_file), "not in file", "replacement")
        assert result.success is False


class TestSearchTools:
    def test_grep_finds_matches(self, temp_workspace):
        (temp_workspace / "code.py").write_text("def test_a():\n    pass\ndef test_b():\n    pass")
        result = grep(r"def test_", str(temp_workspace))
        assert result.success is True
        assert "test_a" in result.output
        assert "test_b" in result.output

    def test_grep_no_matches(self, temp_workspace):
        (temp_workspace / "code.py").write_text("hello world")
        result = grep(r"def test_", str(temp_workspace))
        assert result.success is True
        assert result.output == ""

    def test_list_dir(self, temp_workspace):
        (temp_workspace / "a.py").write_text("")
        (temp_workspace / "b.py").write_text("")
        (temp_workspace / "sub").mkdir()
        result = list_dir(str(temp_workspace))
        assert result.success is True
        assert "a.py" in result.output
        assert "b.py" in result.output
        assert "sub" in result.output

    def test_list_dir_invalid_path(self):
        result = list_dir("/nonexistent/path")
        assert result.success is False


class TestShellTools:
    def test_run_shell_echo(self):
        result = run_shell("echo hello")
        assert result.success is True
        assert "hello" in result.output

    def test_run_shell_failed(self):
        result = run_shell("python -c 'import sys; sys.exit(1)'")
        assert result.success is False
        assert result.exit_code == 1