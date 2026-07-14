import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.agent_loop.stop_judge import StopJudge, StopReason
from src.agent_loop.loop import AgentLoop, LoopResult
from src.llm.base import LLMResponse, ToolCall
from src.llm.mock import MockLLM
from src.tools.registry import ToolRegistry, ToolResult
from src.guardrail.classifier import InterceptResult
from src.guardrail.hitl import HITLStateMachine, HITLDecision


class TestStopJudge:
    def test_test_passed(self):
        judge = StopJudge(max_iterations=10)
        reason = judge.should_stop(iteration=3, test_passed=True, llm_text="done", tool_calls=None)
        assert reason == StopReason.TEST_PASSED

    def test_max_iterations(self):
        judge = StopJudge(max_iterations=5)
        reason = judge.should_stop(iteration=5, test_passed=False, llm_text=None, tool_calls=[ToolCall(name="grep", args={})])
        assert reason == StopReason.MAX_ITERATIONS

    def test_llm_stopped(self):
        judge = StopJudge(max_iterations=10)
        reason = judge.should_stop(iteration=2, test_passed=False, llm_text="Task complete.", tool_calls=None)
        assert reason == StopReason.LLM_STOPPED

    def test_dead_loop(self):
        judge = StopJudge(max_iterations=10)
        for _ in range(4):
            reason = judge.should_stop(iteration=3, test_passed=False, llm_text=None, tool_calls=[ToolCall(name="grep", args={"pattern": "test"})])
        assert reason == StopReason.DEAD_LOOP

    def test_continue(self):
        judge = StopJudge(max_iterations=10)
        reason = judge.should_stop(iteration=2, test_passed=False, llm_text=None, tool_calls=[ToolCall(name="grep", args={})])
        assert reason is None


class TestAgentLoop:
    def test_completes_with_mock_llm(self, temp_workspace):
        mock = MockLLM(responses=[
            LLMResponse(tool_calls=[ToolCall(name="grep", args={"pattern": "def test", "path": "."})]),
            LLMResponse(tool_calls=[ToolCall(name="run_shell", args={"command": "python -m pytest"})]),
        ])
        registry = ToolRegistry()
        registry.register("grep", lambda pattern, path: ToolResult(success=True, output="test_foo"), {"pattern": "str", "path": "str"})
        def fake_shell(command, timeout=120):
            if "pytest" in command:
                return ToolResult(success=True, output="3 passed in 0.10s", exit_code=0)
            return ToolResult(success=True, output="ok")
        registry.register("run_shell", fake_shell, {"command": "str", "timeout": "int"})

        with patch("src.agent_loop.loop.HITLStateMachine") as mock_hitl_cls:
            mock_hitl = MagicMock()
            mock_hitl.check.return_value = HITLDecision.ALLOW
            mock_hitl_cls.return_value = mock_hitl

            loop = AgentLoop(
                llm=mock,
                tools=registry,
                workspace=temp_workspace,
                config={"max_iterations": 10, "timeout": 120, "test_command": "pytest", "sandbox_root": str(temp_workspace)},
            )
            result = loop.run("fix the failing tests")

        assert result.success is True
        assert mock.call_count == 2

    def test_respects_max_iterations(self, temp_workspace):
        responses = []
        for _ in range(5):
            responses.append(LLMResponse(tool_calls=[ToolCall(name="grep", args={"pattern": "test", "path": "."})]))
        mock = MockLLM(responses=responses)

        registry = ToolRegistry()
        registry.register("grep", lambda pattern, path: ToolResult(success=True, output=""), {"pattern": "str", "path": "str"})

        with patch("src.agent_loop.loop.HITLStateMachine") as mock_hitl_cls:
            mock_hitl = MagicMock()
            mock_hitl.check.return_value = HITLDecision.ALLOW
            mock_hitl_cls.return_value = mock_hitl

            loop = AgentLoop(
                llm=mock,
                tools=registry,
                workspace=temp_workspace,
                config={"max_iterations": 3, "timeout": 120, "test_command": "pytest", "sandbox_root": str(temp_workspace)},
            )
            result = loop.run("fix the failing tests")

        assert result.success is False
        assert result.stop_reason == "max_iterations"
        assert mock.call_count <= 3

    def test_stops_on_llm_text_without_tool_calls(self, temp_workspace):
        mock = MockLLM(responses=[
            LLMResponse(text="I have analyzed the problem. The fix is complete.", tool_calls=None),
        ])
        registry = ToolRegistry()

        with patch("src.agent_loop.loop.HITLStateMachine") as mock_hitl_cls:
            mock_hitl = MagicMock()
            mock_hitl.check.return_value = HITLDecision.ALLOW
            mock_hitl_cls.return_value = mock_hitl

            loop = AgentLoop(
                llm=mock,
                tools=registry,
                workspace=temp_workspace,
                config={"max_iterations": 10, "timeout": 120, "test_command": "pytest", "sandbox_root": str(temp_workspace)},
            )
            result = loop.run("analyze the code")

        assert result.stop_reason == "llm_stopped"

    def test_handles_llm_error(self, temp_workspace):
        mock = MockLLM(responses=[
            LLMResponse(error="API error 500: Internal Server Error"),
        ])
        registry = ToolRegistry()

        with patch("src.agent_loop.loop.HITLStateMachine") as mock_hitl_cls:
            mock_hitl = MagicMock()
            mock_hitl.check.return_value = HITLDecision.ALLOW
            mock_hitl_cls.return_value = mock_hitl

            loop = AgentLoop(
                llm=mock,
                tools=registry,
                workspace=temp_workspace,
                config={"max_iterations": 10, "timeout": 120, "test_command": "pytest", "sandbox_root": str(temp_workspace)},
            )
            result = loop.run("fix the bug")

        assert result.success is False
        assert "LLM error" in result.logs[1]

    def test_logs_tool_execution(self, temp_workspace):
        mock = MockLLM(responses=[
            LLMResponse(tool_calls=[ToolCall(name="grep", args={"pattern": "def test", "path": "."})]),
            LLMResponse(text="Done."),
        ])
        registry = ToolRegistry()
        registry.register("grep", lambda pattern, path: ToolResult(success=True, output="test_foo"), {"pattern": "str", "path": "str"})

        with patch("src.agent_loop.loop.HITLStateMachine") as mock_hitl_cls:
            mock_hitl = MagicMock()
            mock_hitl.check.return_value = HITLDecision.ALLOW
            mock_hitl_cls.return_value = mock_hitl

            loop = AgentLoop(
                llm=mock,
                tools=registry,
                workspace=temp_workspace,
                config={"max_iterations": 10, "timeout": 120, "test_command": "pytest", "sandbox_root": str(temp_workspace)},
            )
            result = loop.run("search for tests")

        tool_logs = [l for l in result.logs if "Tool grep" in l]
        assert len(tool_logs) == 1
        assert "True" in tool_logs[0]