"""
机制演示 ①：治理护栏拦截危险动作
在 mock LLM 下确定性复现：agent 尝试执行 rm -rf → 被护栏拦截 → 等待人工确认
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.guardrail.classifier import classify_action


def demo():
    print("=" * 60)
    print("机制演示 ①：护栏拦截危险动作")
    print("=" * 60)

    # 安全命令
    safe = classify_action("run_shell", {"command": "python -m pytest"})
    print(f"\n[Safe] pytest: level={safe.level}, blocked={safe.blocked}")

    # 危险命令
    dangerous = classify_action("run_shell", {"command": "rm -rf /"})
    print(f"[Danger] rm -rf: level={dangerous.level}, blocked={dangerous.blocked}, reason={dangerous.reason}")

    # 更多危险命令
    for cmd in ["git push --force origin main", "DROP TABLE users", "chmod 777 /etc/passwd"]:
        result = classify_action("run_shell", {"command": cmd})
        print(f"[Danger] {cmd}: level={result.level}, blocked={result.blocked}")

    assert dangerous.level == 3
    assert dangerous.blocked is True
    print("\n[PASS] 护栏拦截演示通过：危险命令被正确拦截")


if __name__ == "__main__":
    demo()