import re
from dataclasses import dataclass


@dataclass
class FailureInfo:
    type: str
    file: str
    line: int | None
    message: str
    expected: str | None = None
    actual: str | None = None
    strategy: str = ""


CLASSIFICATION_RULES = [
    (re.compile(r"SyntaxError|IndentationError", re.IGNORECASE), "SyntaxError",
     "定位报错行号，检查语法和缩进错误"),
    (re.compile(r"ModuleNotFoundError|ImportError", re.IGNORECASE), "ImportError",
     "检查包名拼写以及依赖是否已安装"),
    (re.compile(r"AssertionError", re.IGNORECASE), "AssertionError",
     "对比期望值与实际值差异，检查被测试函数的实现逻辑"),
    (re.compile(r"AttributeError", re.IGNORECASE), "AttributeError",
     "检查对象类型，确认属性或方法名拼写是否正确"),
    (re.compile(r"TypeError", re.IGNORECASE), "TypeError",
     "检查函数参数类型和数量是否匹配"),
    (re.compile(r"timed?[\s-]*out", re.IGNORECASE), "Timeout",
     "命令执行超时，建议优化代码或增加超时时间"),
    (re.compile(r"NameError", re.IGNORECASE), "NameError",
     "检查变量或函数名拼写，确认是否已定义"),
    (re.compile(r"ValueError", re.IGNORECASE), "ValueError",
     "检查传入参数的值是否在合法范围内"),
]


def classify_failure(failure: dict) -> FailureInfo:
    message = failure.get("message", "")
    for pattern, error_type, strategy in CLASSIFICATION_RULES:
        if pattern.search(message):
            return FailureInfo(
                type=error_type,
                file=failure.get("file", ""),
                line=failure.get("line"),
                message=message,
                strategy=strategy,
            )

    return FailureInfo(
        type="UnknownError",
        file=failure.get("file", ""),
        line=failure.get("line"),
        message=message,
        strategy="原文回灌，由 LLM 自主分析",
    )