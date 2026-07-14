import sys
from enum import Enum
from src.guardrail.classifier import InterceptResult


class HITLDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ALWAYS = "always"


class HITLStateMachine:
    def __init__(self, timeout: int = 60):
        self.graylist: set[str] = set()
        self.timeout = timeout

    def check(self, result: InterceptResult) -> HITLDecision | None:
        if result.level < 3:
            return HITLDecision.ALLOW
        if not sys.stdin.isatty():
            return HITLDecision.DENY
        return None

    def request_approval(self, result: InterceptResult) -> HITLDecision:
        if not sys.stdin.isatty():
            print(f"[HITL] Non-interactive mode: auto-denying '{result.reason}'")
            return HITLDecision.DENY

        print(f"\n[HITL] Level {result.level} action blocked: {result.reason}")
        try:
            while True:
                choice = input("Allow? (y=yes / n=no / always=permanently allow): ").strip().lower()
                if choice == "y":
                    return HITLDecision.ALLOW
                elif choice == "n":
                    return HITLDecision.DENY
                elif choice == "always":
                    return HITLDecision.ALWAYS
                else:
                    print("Invalid input. Enter y, n, or always.")
        except (EOFError, KeyboardInterrupt):
            return HITLDecision.DENY