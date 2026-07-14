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

    def register(self, name: str, func: Callable, params: dict[str, str], description: str = "") -> None:
        self._tools[name] = {"func": func, "params": params, "description": description}

    def list_tools(self) -> list[dict]:
        tools = []
        for name, info in self._tools.items():
            properties = {}
            required = []
            for pname, ptype in info["params"].items():
                is_optional = "?" in ptype
                clean_type = ptype.replace("?", "")
                type_map = {"str": "string", "int": "integer", "bool": "boolean", "float": "number"}
                json_type = type_map.get(clean_type, "string")
                properties[pname] = {"type": json_type}
                if not is_optional:
                    required.append(pname)
            tools.append({
                "name": name,
                "description": info.get("description") or f"Tool: {name}",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
        return tools

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