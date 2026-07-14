from pathlib import Path
from src.tools.registry import ToolResult


def read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> ToolResult:
    p = Path(path)
    if not p.exists():
        return ToolResult(success=False, output="", error=f"File not found: {path}")
    try:
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if start_line is not None:
            start = max(0, start_line - 1)
            end = min(len(lines), end_line) if end_line is not None else len(lines)
            lines = lines[start:end]
        return ToolResult(success=True, output="".join(lines))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def write_file(path: str, content: str) -> ToolResult:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(success=True, output=f"Written {len(content)} bytes to {path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def edit_file(path: str, search: str, replace: str, replace_all: bool = False) -> ToolResult:
    p = Path(path)
    if not p.exists():
        return ToolResult(success=False, output="", error=f"File not found: {path}")
    try:
        content = p.read_text(encoding="utf-8")
        if search not in content:
            return ToolResult(success=False, output="", error=f"Search text not found in {path}")
        count = content.count(search) if replace_all else 1
        new_content = content.replace(search, replace, -1 if replace_all else 1)
        p.write_text(new_content, encoding="utf-8")
        return ToolResult(success=True, output=f"Replaced {count} occurrence(s) in {path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))