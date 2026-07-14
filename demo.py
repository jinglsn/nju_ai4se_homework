import time
import pyautogui


def auto_press_enter(interval: int = 10):
    """
    每隔 interval 秒自动按一次回车键
    按 Ctrl + C 可终止程序

    """
    print(f"自动回车程序已启动，每 {interval} 秒按一次 Enter")
    print("提示：请确保目标窗口处于前台激活状态")
    print("按 Ctrl + C 可停止程序\n")

    try:
        while True:
            # 模拟按下并松开回车键

            pyautogui.press("enter")
            print(f"[{time.strftime('%H:%M:%S')}] 已按下 Enter")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n程序已手动停止")


if __name__ == "__main__":
    # 这里修改数字即可调整间隔秒数
    auto_press_enter(interval=10)