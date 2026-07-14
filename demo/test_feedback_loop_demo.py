"""
机制演示 ②：反馈闭环使 agent 收到反馈后改变下一步动作
注入一次测试失败 → 反馈闭环解析分类 → 结构化反馈回灌 → agent 根据反馈改变行为
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.mock import MockLLM
from src.llm.base import LLMResponse, ToolCall
from src.tools.registry import ToolRegistry, ToolResult
from src.agent_loop.loop import AgentLoop
from unittest.mock import patch, MagicMock
from src.guardrail.hitl import HITLDecision


def demo():
    print("=" * 60)
    print("机制演示 ②：反馈闭环驱动自我修正")
    print("=" * 60)

    mock = MockLLM(responses=[
        LLMResponse(tool_calls=[ToolCall(name="run_shell", args={"command": "python -m pytest"})]),
        LLMResponse(tool_calls=[ToolCall(name="read_file", args={"path": "test_calc.py"})]),
        LLMResponse(tool_calls=[ToolCall(name="edit_file", args={"path": "calc.py", "search": "return a - b", "replace": "return a + b"})]),
        LLMResponse(tool_calls=[ToolCall(name="run_shell", args={"command": "python -m pytest"})]),
    ])

    registry = ToolRegistry()
    call_count = {"count": 0}

    def fake_shell(command, timeout=120):
        call_count["count"] += 1
        if call_count["count"] == 1:
            return ToolResult(success=False, output="""test_calc.py::test_add FAILED
==================================== FAILURES ====================================
assert calc.add(1, 2) == 3
AssertionError: assert 3 == 4""", exit_code=1)
        return ToolResult(success=True, output="3 passed in 0.10s", exit_code=0)

    registry.register("run_shell", fake_shell, {"command": "str", "timeout": "int?"})
    registry.register("read_file", lambda path: ToolResult(success=True, output="def add(a,b): return a-b"), {"path": "str"})
    registry.register("edit_file", lambda path, search, replace: ToolResult(success=True, output="replaced"), {"path": "str", "search": "str", "replace": "str"})

    with patch("src.agent_loop.loop.HITLStateMachine") as mock_hitl_cls:
        mock_hitl = MagicMock()
        mock_hitl.check.return_value = HITLDecision.ALLOW
        mock_hitl_cls.return_value = mock_hitl

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / ".harness").mkdir()
            loop = AgentLoop(
                llm=mock,
                tools=registry,
                workspace=workspace,
                config={"max_iterations": 10, "timeout": 120, "test_command": "pytest", "sandbox_root": str(workspace)},
            )
            result = loop.run("fix the failing tests")

    print(f"\nResult: success={result.success}, stop_reason={result.stop_reason}")
    print(f"Iterations: {result.iterations}")
    assert mock.call_count >= 2, "Agent should make at least 2 LLM calls"
    print("\n[PASS] 反馈闭环演示通过：测试失败 -> 分类 -> 回灌 -> agent 调整行为")


if __name__ == "__main__":
    demo()