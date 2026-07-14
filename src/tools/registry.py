from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    def register(self, name: str, func: Callable, params: dict[str, str]) -> None:
        self._tools[name] = {"func": func, "params": params}

    def list_tools(self) -> list[dict]:
        return [
            {"name": name, "parameters": info["params"]}
            for name, info in self._tools.items()
        ]

    def execute(self, name: str, args: dict[str, Any]) -> ToolResult:
        if name not in self._tools:
            return ToolResult(success=False, output="", error=f"Unknown tool: {name}")
        tool = self._tools[name]
        try:
            return tool["func"](**args)
        except TypeError as e:
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))