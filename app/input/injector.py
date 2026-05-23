from __future__ import annotations

import time


class InputInjector:
    def copy(self, text: str) -> None:
        try:
            import pyperclip
        except ImportError as exc:
            raise RuntimeError("缺少 pyperclip，请先安装依赖：pip install -r requirements.txt") from exc

        pyperclip.copy(text)

    def paste(self, text: str) -> None:
        self.copy(text)
        time.sleep(0.05)

        try:
            import pyautogui
        except ImportError as exc:
            raise RuntimeError("缺少 pyautogui，请先安装依赖：pip install -r requirements.txt") from exc

        pyautogui.hotkey("ctrl", "v")
