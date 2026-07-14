import re
from dataclasses import dataclass


@dataclass
class InterceptResult:
    level: int
    blocked: bool
    reason: str = ""


LEVEL1_TOOLS = {"read_file", "grep", "list_dir"}
LEVEL1_COMMANDS = [
    re.compile(r"^(python|python3)\s+-m\s+pytest"),
    re.compile(r"^(python|python3)\s+-m\s+mypy"),
    re.compile(r"^(pytest|flake8|mypy|black|isort|ruff)"),
    re.compile(r"^(echo|cat|head|tail|ls|dir|pwd|whoami|date)"),
]
LEVEL3_PATTERNS = [
    (re.compile(r"\brm\s+-rf\b"), "rm -rf is destructive"),
    (re.compile(r"\brm\s+-r\b"), "rm -r is destructive"),
    (re.compile(r"\bgit\s+push\s+.*--force"), "git push --force is irreversible"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard is destructive"),
    (re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE), "DROP TABLE is destructive"),
    (re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE), "DROP DATABASE is destructive"),
    (re.compile(r"\bchmod\s+777\b"), "chmod 777 is a security risk"),
    (re.compile(r"\bchown\b"), "chown may be dangerous"),
    (re.compile(r"\b(shutdown|reboot|systemctl\s+stop)\b"), "system command is dangerous"),
    (re.compile(r"\bdel\s+/[fsq]\b"), "Windows destructive delete"),
    (re.compile(r"\bformat\s+[a-zA-Z]:\b", re.IGNORECASE), "disk format is destructive"),
]


def classify_action(tool_name: str, args: dict) -> InterceptResult:
    if tool_name in LEVEL1_TOOLS:
        return InterceptResult(level=1, blocked=False)

    if tool_name == "run_shell":
        command = args.get("command", "")
        for pattern, reason in LEVEL3_PATTERNS:
            if pattern.search(command):
                return InterceptResult(level=3, blocked=True, reason=reason)
        for pattern in LEVEL1_COMMANDS:
            if pattern.search(command):
                return InterceptResult(level=1, blocked=False)
        return InterceptResult(level=2, blocked=False, reason="Unclassified shell command")

    if tool_name in ("write_file", "edit_file"):
        return InterceptResult(level=2, blocked=False)

    return InterceptResult(level=2, blocked=False, reason=f"Unknown tool: {tool_name}")