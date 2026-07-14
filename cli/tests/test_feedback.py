import pytest
from src.feedback.parser import parse_test_output
from src.feedback.classifier import classify_failure, FailureInfo
from src.feedback.builder import build_feedback, FeedbackResult

PYTEST_FAIL_OUTPUT = """
============================= test session starts ==============================
test_calc.py::test_add FAILED
test_calc.py::test_sub PASSED
=================================== FAILURES ===================================
__________________________________ test_add ___________________________________
    def test_add():
>       assert calc.add(1, 2) == 4
E       assert 3 == 4
E        +  where 3 = calc.add(1, 2)
test_calc.py:5: AssertionError
========================= 1 failed, 1 passed in 0.12s =========================
"""

UNITTEST_FAIL_OUTPUT = """
FAIL: test_add (test_calc)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "test_calc.py", line 5, in test_add
    self.assertEqual(calc.add(1, 2), 4)
AssertionError: 3 != 4
"""


class TestParser:
    def test_pytest_format(self):
        failures = parse_test_output(PYTEST_FAIL_OUTPUT)
        assert len(failures) == 1
        assert failures[0]["file"] == "test_calc.py"
        assert "assert" in failures[0]["message"].lower()

    def test_empty_output(self):
        assert parse_test_output("") == []

    def test_all_pass(self):
        assert parse_test_output("3 passed in 0.10s") == []

    def test_unittest_format(self):
        failures = parse_test_output(UNITTEST_FAIL_OUTPUT)
        assert len(failures) >= 1

    def test_fallback_on_error_keyword(self):
        failures = parse_test_output("ERROR: something went wrong")
        assert len(failures) >= 1


class TestClassifier:
    def test_assertion_error(self):
        info = classify_failure({"file": "test_calc.py", "line": 5, "message": "assert 3 == 4\nAssertionError"})
        assert info.type == "AssertionError"
        assert "期望值" in info.strategy

    def test_syntax_error(self):
        info = classify_failure({"file": "calc.py", "line": 10, "message": "SyntaxError: invalid syntax"})
        assert info.type == "SyntaxError"

    def test_import_error(self):
        info = classify_failure({"file": "test.py", "line": 1, "message": "ModuleNotFoundError: No module named 'requests'"})
        assert info.type == "ImportError"

    def test_attribute_error(self):
        info = classify_failure({"file": "calc.py", "line": 8, "message": "AttributeError: 'int' object has no attribute 'add'"})
        assert info.type == "AttributeError"

    def test_type_error(self):
        info = classify_failure({"file": "calc.py", "line": 5, "message": "TypeError: unsupported operand type(s) for +"})
        assert info.type == "TypeError"

    def test_timeout(self):
        info = classify_failure({"file": "", "line": None, "message": "Command timed out after 120s"})
        assert info.type == "Timeout"

    def test_name_error(self):
        info = classify_failure({"file": "x.py", "line": 3, "message": "NameError: name 'foo' is not defined"})
        assert info.type == "NameError"

    def test_value_error(self):
        info = classify_failure({"file": "x.py", "line": 7, "message": "ValueError: invalid literal"})
        assert info.type == "ValueError"

    def test_unknown_error(self):
        info = classify_failure({"file": "x.py", "line": 1, "message": "weird error XYZ"})
        assert info.type == "UnknownError"


class TestBuilder:
    def test_with_failure(self):
        result = build_feedback(PYTEST_FAIL_OUTPUT)
        assert result.test_result == "FAIL"
        assert len(result.failures) == 1
        assert result.failures[0].type == "AssertionError"

    def test_all_pass(self):
        result = build_feedback("3 passed in 0.10s")
        assert result.test_result == "PASS"
        assert len(result.failures) == 0

    def test_regression_detection(self):
        previous = "test_calc.py::test_add PASSED\n3 passed"
        result = build_feedback(PYTEST_FAIL_OUTPUT, previous)
        assert result.regression is True

    def test_no_regression_without_previous(self):
        result = build_feedback(PYTEST_FAIL_OUTPUT, None)
        assert result.regression is False