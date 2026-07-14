import pytest
from pathlib import Path
from unittest.mock import patch
from src.guardrail.classifier import classify_action, InterceptResult
from src.guardrail.sandbox import Sandbox
from src.guardrail.hitl import HITLStateMachine, HITLDecision


class TestClassifier:
    def test_read_file_level1(self):
        assert classify_action("read_file", {"path": "test.py"}).level == 1

    def test_grep_level1(self):
        assert classify_action("grep", {"pattern": "def", "path": "src/"}).level == 1

    def test_list_dir_level1(self):
        assert classify_action("list_dir", {"path": "."}).level == 1

    def test_write_file_level2(self):
        result = classify_action("write_file", {"path": "src/new.py", "content": "x=1"})
        assert result.level == 2
        assert result.blocked is False

    def test_run_shell_pytest_level1(self):
        assert classify_action("run_shell", {"command": "python -m pytest"}).level == 1

    def test_run_shell_pip_install_level2(self):
        assert classify_action("run_shell", {"command": "pip install requests"}).level == 2

    def test_run_shell_rm_rf_level3(self):
        result = classify_action("run_shell", {"command": "rm -rf /"})
        assert result.level == 3
        assert result.blocked is True

    def test_run_shell_git_push_force_level3(self):
        result = classify_action("run_shell", {"command": "git push --force origin main"})
        assert result.level == 3
        assert result.blocked is True

    def test_run_shell_drop_table_level3(self):
        result = classify_action("run_shell", {"command": "DROP TABLE users"})
        assert result.level == 3
        assert result.blocked is True

    def test_run_shell_chmod_777_level3(self):
        assert classify_action("run_shell", {"command": "chmod 777 /etc/passwd"}).level == 3


class TestSandbox:
    def test_path_inside_root(self):
        sandbox = Sandbox(Path("/workspace"))
        assert sandbox.verify_path("/workspace/src/test.py") is True

    def test_path_outside_root(self):
        sandbox = Sandbox(Path("/workspace"))
        assert sandbox.verify_path("/etc/passwd") is False


class TestHITL:
    def test_approve(self):
        hitl = HITLStateMachine()
        with patch("sys.stdin.isatty", return_value=True):
            with patch("builtins.input", return_value="y"):
                assert hitl.request_approval(InterceptResult(level=3, blocked=True, reason="rm -rf")) == HITLDecision.ALLOW

    def test_deny(self):
        hitl = HITLStateMachine()
        with patch("sys.stdin.isatty", return_value=True):
            with patch("builtins.input", return_value="n"):
                assert hitl.request_approval(InterceptResult(level=3, blocked=True, reason="rm -rf")) == HITLDecision.DENY

    def test_always(self):
        hitl = HITLStateMachine()
        with patch("sys.stdin.isatty", return_value=True):
            with patch("builtins.input", return_value="always"):
                assert hitl.request_approval(InterceptResult(level=3, blocked=True, reason="rm -rf")) == HITLDecision.ALWAYS

    def test_level2_bypass(self):
        hitl = HITLStateMachine()
        assert hitl.check(InterceptResult(level=2, blocked=False)) == HITLDecision.ALLOW

    def test_level3_requires_confirm(self):
        hitl = HITLStateMachine()
        with patch("sys.stdin.isatty", return_value=True):
            assert hitl.check(InterceptResult(level=3, blocked=True, reason="rm -rf")) is None