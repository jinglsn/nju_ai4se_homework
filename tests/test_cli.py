import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.cli import build_parser


class TestParser:
    def test_run_command(self):
        parser = build_parser()
        args = parser.parse_args(["run", "fix the bug"])
        assert args.command == "run"
        assert args.task == "fix the bug"

    def test_memory_list(self):
        parser = build_parser()
        args = parser.parse_args(["memory", "list"])
        assert args.command == "memory"
        assert args.subcommand == "list"

    def test_memory_clear(self):
        parser = build_parser()
        args = parser.parse_args(["memory", "clear"])
        assert args.subcommand == "clear"

    def test_memory_set(self):
        parser = build_parser()
        args = parser.parse_args(["memory", "set", "test_command", "pytest -x"])
        assert args.subcommand == "set"
        assert args.key == "test_command"
        assert args.value == "pytest -x"

    def test_keyring_status(self):
        parser = build_parser()
        args = parser.parse_args(["keyring", "status"])
        assert args.command == "keyring"
        assert args.subcommand == "status"

    def test_keyring_set(self):
        parser = build_parser()
        args = parser.parse_args(["keyring", "set"])
        assert args.subcommand == "set"

    def test_config_show(self):
        parser = build_parser()
        args = parser.parse_args(["config", "show"])
        assert args.command == "config"
        assert args.subcommand == "show"


class TestCommands:
    def test_cmd_memory_set(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()
        from src.memory.store import MemoryStore
        store = MemoryStore(harness_dir)
        data = store.load()
        data["conventions"]["test_command"] = "pytest -x"
        store.save(data)

        loaded = store.load()
        assert loaded["conventions"]["test_command"] == "pytest -x"

    def test_cmd_memory_clear(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()
        from src.memory.store import MemoryStore
        store = MemoryStore(harness_dir)
        store.add_fix_record({"error_type": "test"})
        assert store.load()["fix_history"]

        store.clear()
        assert not store.load()["fix_history"]

    def test_cmd_run_with_mock(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".harness").mkdir()

        from src.llm.mock import MockLLM
        from src.llm.base import LLMResponse, ToolCall
        from src.tools.registry import ToolRegistry, ToolResult
        from src.agent_loop.loop import AgentLoop

        mock = MockLLM(responses=[
            LLMResponse(tool_calls=[ToolCall(name="grep", args={"pattern": "test", "path": "."})]),
            LLMResponse(text="Done."),
        ])
        registry = ToolRegistry()
        registry.register("grep", lambda pattern, path: ToolResult(success=True, output=""), {"pattern": "str", "path": "str"})

        with patch("src.agent_loop.loop.HITLStateMachine") as mock_hitl_cls:
            mock_hitl = MagicMock()
            mock_hitl.check.return_value = __import__("src.guardrail.hitl", fromlist=["HITLDecision"]).HITLDecision.ALLOW
            mock_hitl_cls.return_value = mock_hitl

            loop = AgentLoop(
                llm=mock,
                tools=registry,
                workspace=tmp_path,
                config={"max_iterations": 10, "timeout": 120, "test_command": "pytest", "sandbox_root": str(tmp_path)},
            )
            result = loop.run("search")
            assert result.iterations >= 1