import pytest
from pathlib import Path
from src.agent_loop.loop import AgentLoop
from src.llm.base import LLMResponse, ToolCall
from src.llm.mock import MockLLM
from src.tools.registry import ToolRegistry, ToolResult


@pytest.mark.asyncio
async def test_run_stream_yields_iteration_events():
    mock_llm = MockLLM(responses=[
        LLMResponse(text="let me check", tool_calls=[
            ToolCall(name="list_dir", args={"path": "."})
        ]),
        LLMResponse(text="done"),
    ])
    registry = ToolRegistry()
    registry.register("list_dir", lambda path: ToolResult(success=True, output="file1.py"), {"path": "str"})

    loop = AgentLoop(llm=mock_llm, tools=registry, workspace=Path("/tmp"), config={})
    events = []
    async for event in loop.run_stream("find the bug"):
        events.append(event)

    types = [e["type"] for e in events]
    assert "iteration" in types
    assert "tool_start" in types
    assert "tool_result" in types
    assert "stop" in types


@pytest.mark.asyncio
async def test_run_stream_stops_on_test_passed():
    mock_llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[
            ToolCall(name="run_shell", args={"command": "pytest"})
        ]),
    ])
    registry = ToolRegistry()
    registry.register("run_shell", lambda command, timeout=120: ToolResult(
        success=True, output="1 passed", exit_code=0
    ), {"command": "str", "timeout": "int?"})

    loop = AgentLoop(llm=mock_llm, tools=registry, workspace=Path("/tmp"), config={})
    events = []
    async for event in loop.run_stream("run tests"):
        events.append(event)

    stop_events = [e for e in events if e["type"] == "stop"]
    assert len(stop_events) == 1
    assert stop_events[0]["reason"] == "test_passed"


@pytest.mark.asyncio
async def test_run_stream_handles_llm_error():
    mock_llm = MockLLM(responses=[
        LLMResponse(error="API key not configured"),
    ])
    registry = ToolRegistry()
    loop = AgentLoop(llm=mock_llm, tools=registry, workspace=Path("/tmp"), config={})
    events = []
    async for event in loop.run_stream("do something"):
        events.append(event)

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1