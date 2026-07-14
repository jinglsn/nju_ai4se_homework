import asyncio
import sys
from enum import Enum
from src.guardrail.classifier import InterceptResult


class HITLDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ALWAYS = "always"


class HITLStateMachine:
    def __init__(self, timeout: int = 60, web_mode: bool = False):
        self.graylist: set[str] = set()
        self.timeout = timeout
        self.web_mode = web_mode
        self._pending_future: asyncio.Future | None = None

    def check(self, result: InterceptResult) -> HITLDecision | None:
        if result.level < 3:
            return HITLDecision.ALLOW
        if self.web_mode:
            return None
        if not sys.stdin.isatty():
            return HITLDecision.DENY
        return None

    def wait_for_decision(self) -> asyncio.Future:
        loop = asyncio.get_event_loop()
        self._pending_future = loop.create_future()
        if self.timeout > 0:
            loop.call_later(self.timeout, self._on_timeout)
        return self._pending_future

    def resolve_decision(self, approved: bool) -> None:
        if self._pending_future and not self._pending_future.done():
            self._pending_future.set_result(approved)

    def _on_timeout(self) -> None:
        if self._pending_future and not self._pending_future.done():
            self._pending_future.set_result(False)

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