from dataclasses import dataclass, field
from src.feedback.parser import parse_test_output
from src.feedback.classifier import classify_failure, FailureInfo


@dataclass
class FeedbackResult:
    test_result: str  # "PASS" | "FAIL" | "TIMEOUT" | "ERROR"
    failures: list[FailureInfo] = field(default_factory=list)
    summary: str = ""
    regression: bool = False


def build_feedback(test_output: str, previous_test_output: str | None = None) -> FeedbackResult:
    raw_failures = parse_test_output(test_output)

    if not raw_failures:
        return FeedbackResult(test_result="PASS", summary="All tests passed")

    failures = [classify_failure(f) for f in raw_failures]

    total = len(raw_failures)
    failure_names = [f.get("file", "") for f in raw_failures]
    summary = f"{total} tests failed: {', '.join(failure_names)}"

    regression = False
    if previous_test_output:
        prev_failures = parse_test_output(previous_test_output)
        prev_files = {f.get("file") for f in prev_failures}
        for f in raw_failures:
            if f.get("file") and f.get("file") not in prev_files:
                regression = True
                break

    return FeedbackResult(
        test_result="FAIL",
        failures=failures,
        summary=summary,
        regression=regression,
    )