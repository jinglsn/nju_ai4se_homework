import re
import subprocess
from src.tools.registry import ToolResult

BLOCKED_PATTERNS = [
    (re.compile(r"rm\s+-rf\s+/"), "rm -rf / is blocked"),
    (re.compile(r"dd\s+if="), "dd is blocked"),
    (re.compile(r"mkfs"), "mkfs is blocked"),
    (re.compile(r"shutdown"), "shutdown is blocked"),
    (re.compile(r"reboot"), "reboot is blocked"),
    (re.compile(r"chmod\s+777"), "chmod 777 is blocked"),
    (re.compile(r">\s*/dev/"), "redirect to /dev/ is blocked"),
    (re.compile(r"curl.*\|\s*(ba)?sh"), "curl | bash is blocked"),
    (re.compile(r"wget.*\|\s*(ba)?sh"), "wget | bash is blocked"),
    (re.compile(r"sudo\s"), "sudo is blocked"),
    (re.compile(r"chown\s"), "chown is blocked"),
    (re.compile(r":\(\)\s*\{"), "fork bomb blocked"),
]


def run_shell(command: str, timeout: int = 120, workspace: str | None = None) -> ToolResult:
    for pattern, reason in BLOCKED_PATTERNS:
        if pattern.search(command):
            return ToolResult(success=False, output="", error=f"Blocked: {reason}")

    try:
        kwargs = dict(shell=True, capture_output=True, text=True, timeout=timeout)
        if workspace:
            kwargs["cwd"] = workspace
        result = subprocess.run(command, **kwargs)
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