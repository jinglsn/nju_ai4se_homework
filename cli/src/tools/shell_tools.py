import subprocess
from src.tools.registry import ToolResult


def run_shell(command: str, timeout: int = 120) -> ToolResult:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        return ToolResult(
            success=result.returncode == 0,
            output=output.strip() or "(no output)",
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, output="", error=f"Command timed out after {timeout}s", exit_code=-1)
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e), exit_code=-1)