from __future__ import annotations

import time

from app.errors import DependencyMissingError, InputActionError


class InputInjector:
    def copy(self, text: str) -> None:
        try:
            import pyperclip
        except ImportError as exc:
            raise DependencyMissingError("pyperclip", "pip install -r requirements.txt") from exc

        try:
            pyperclip.copy(text)
        except Exception as exc:
            raise InputActionError(f"复制到剪贴板失败：{exc}") from exc

    def paste(self, text: str) -> None:
        self.copy(text)
        time.sleep(0.05)

        try:
            import pyautogui
        except ImportError as exc:
            raise DependencyMissingError("pyautogui", "pip install -r requirements.txt") from exc

        try:
            pyautogui.hotkey("ctrl", "v")
        except Exception as exc:
            raise InputActionError(f"粘贴到当前输入位置失败：{exc}") from exc
