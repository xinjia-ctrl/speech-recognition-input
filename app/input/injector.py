from __future__ import annotations

import ctypes
import os
import time
from collections.abc import Iterable

from app.errors import DependencyMissingError, InputActionError


class InputInjector:
    def __init__(self) -> None:
        self._target_hwnd: int | None = None

    def remember_target_window(self, excluded_handles: Iterable[int] = ()) -> None:
        hwnd = _get_foreground_window()
        if not hwnd:
            return
        if hwnd in set(excluded_handles):
            return
        if _window_process_id(hwnd) == os.getpid():
            return
        self._target_hwnd = hwnd

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
        self._restore_target_window()
        time.sleep(0.15)

        try:
            import pyautogui
        except ImportError as exc:
            raise DependencyMissingError("pyautogui", "pip install -r requirements.txt") from exc

        try:
            pyautogui.hotkey("ctrl", "v")
        except Exception as exc:
            raise InputActionError(f"粘贴到当前输入位置失败：{exc}") from exc

    def _restore_target_window(self) -> None:
        if self._target_hwnd is None or not _is_window(self._target_hwnd):
            return
        try:
            user32 = ctypes.windll.user32
            user32.ShowWindow(self._target_hwnd, 9)
            user32.SetForegroundWindow(self._target_hwnd)
        except Exception:
            return


def _get_foreground_window() -> int:
    try:
        return int(ctypes.windll.user32.GetForegroundWindow())
    except Exception:
        return 0


def _is_window(hwnd: int) -> bool:
    try:
        return bool(ctypes.windll.user32.IsWindow(hwnd))
    except Exception:
        return False


def _window_process_id(hwnd: int) -> int:
    try:
        process_id = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        return int(process_id.value)
    except Exception:
        return 0
