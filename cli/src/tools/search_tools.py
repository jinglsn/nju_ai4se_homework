import re
from pathlib import Path
from src.tools.registry import ToolResult


def grep(pattern: str, path: str) -> ToolResult:
    p = Path(path)
    if not p.exists():
        return ToolResult(success=False, output="", error=f"Path not found: {path}")
    try:
        matches = []
        files = [p] if p.is_file() else list(p.rglob("*"))
        for f in files:
            if not f.is_file():
                continue
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    if re.search(pattern, line):
                        matches.append(f"{f}:{i}: {line}")
            except Exception:
                continue
        return ToolResult(success=True, output="\n".join(matches))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def list_dir(path: str, depth: int = 3) -> ToolResult:
    p = Path(path)
    if not p.exists():
        return ToolResult(success=False, output="", error=f"Path not found: {path}")
    try:
        lines = []
        for item in sorted(p.iterdir()):
            prefix = "[D]" if item.is_dir() else "[F]"
            lines.append(f"{prefix} {item.name}")
        return ToolResult(success=True, output="\n".join(lines))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))