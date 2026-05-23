from __future__ import annotations

from collections.abc import Callable


class GlobalHotkey:
    def __init__(self, hotkey: str, callback: Callable[[], None]) -> None:
        self.hotkey = hotkey
        self.callback = callback
        self._listener = None

    def start(self) -> bool:
        try:
            from pynput import keyboard
        except ImportError:
            return False

        normalized = self._normalize(self.hotkey)
        self._listener = keyboard.GlobalHotKeys({normalized: self.callback})
        self._listener.start()
        return True

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    @staticmethod
    def _normalize(hotkey: str) -> str:
        parts = [part.strip().lower() for part in hotkey.split("+") if part.strip()]
        mapped = []
        for part in parts:
            if part in {"ctrl", "alt", "shift"}:
                mapped.append(f"<{part}>")
            else:
                mapped.append(part)
        return "+".join(mapped)
