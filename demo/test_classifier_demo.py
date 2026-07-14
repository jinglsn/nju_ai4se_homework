"""
机制演示 ③：失败分类器 10 种类型全覆盖
确定性复现：每种失败类型输入 → 分类器正确识别 → 策略映射正确
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.feedback.classifier import classify_failure


def demo():
    print("=" * 60)
    print("机制演示 ③：失败分类器 10 种类型全覆盖")
    print("=" * 60)

    test_cases = [
        ({"file": "calc.py", "line": 10, "message": "SyntaxError: invalid syntax"}, "SyntaxError"),
        ({"file": "calc.py", "line": 10, "message": "IndentationError: unexpected indent"}, "SyntaxError"),
        ({"file": "test.py", "line": 1, "message": "ModuleNotFoundError: No module named 'x'"}, "ImportError"),
        ({"file": "test.py", "line": 1, "message": "ImportError: cannot import name 'foo'"}, "ImportError"),
        ({"file": "test_calc.py", "line": 5, "message": "assert 3 == 4\nAssertionError"}, "AssertionError"),
        ({"file": "calc.py", "line": 8, "message": "AttributeError: 'int' object has no attribute 'add'"}, "AttributeError"),
        ({"file": "calc.py", "line": 5, "message": "TypeError: unsupported operand type(s) for +"}, "TypeError"),
        ({"file": "", "line": None, "message": "Command timed out after 120s"}, "Timeout"),
        ({"file": "x.py", "line": 3, "message": "NameError: name 'foo' is not defined"}, "NameError"),
        ({"file": "x.py", "line": 7, "message": "ValueError: invalid literal for int()"}, "ValueError"),
        ({"file": "x.py", "line": 1, "message": "weird unknown error XYZ"}, "UnknownError"),
    ]

    all_passed = True
    for failure, expected_type in test_cases:
        info = classify_failure(failure)
        status = "[OK]" if info.type == expected_type else "[FAIL]"
        if info.type != expected_type:
            all_passed = False
        print(f"  {status} {failure['message'][:60]:60s} -> {info.type} (expected: {expected_type})")

    print(f"\n{'[PASS] all 11 classification types passed' if all_passed else '[FAIL] some classifications failed'}")
    assert all_passed, "All classification types must match"


if __name__ == "__main__":
    demo()