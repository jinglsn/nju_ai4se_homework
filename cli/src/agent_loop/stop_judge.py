from enum import Enum


class StopReason(Enum):
    TEST_PASSED = "test_passed"
    MAX_ITERATIONS = "max_iterations"
    LLM_STOPPED = "llm_stopped"
    DEAD_LOOP = "dead_loop"


class StopJudge:
    def __init__(self, max_iterations: int = 10, dead_loop_threshold: int = 3):
        self.max_iterations = max_iterations
        self.dead_loop_threshold = dead_loop_threshold
        self._tool_call_history: list[frozenset] = []
        self._consecutive_same = 0

    def should_stop(self, iteration: int, test_passed: bool, llm_text: str | None, tool_calls: list | None) -> StopReason | None:
        if test_passed:
            return StopReason.TEST_PASSED

        if iteration >= self.max_iterations:
            return StopReason.MAX_ITERATIONS

        if llm_text and not tool_calls:
            return StopReason.LLM_STOPPED

        if tool_calls:
            call_pattern = frozenset(
                (tc.name, frozenset(tc.args.items()) if hasattr(tc, 'args') else frozenset())
                for tc in tool_calls
            )
            self._tool_call_history.append(call_pattern)
            if len(self._tool_call_history) >= self.dead_loop_threshold + 1:
                recent = self._tool_call_history[-self.dead_loop_threshold:]
                if all(r == recent[0] for r in recent):
                    return StopReason.DEAD_LOOP

        return None