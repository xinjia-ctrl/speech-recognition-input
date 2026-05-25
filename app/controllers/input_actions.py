from __future__ import annotations

from dataclasses import dataclass

from app.errors import user_error_message
from app.input import InputInjector


@dataclass(slots=True)
class InputActionResult:
    ok: bool
    message: str
    error: str = ""


class InputController:
    def __init__(self, injector: InputInjector | None = None) -> None:
        self.injector = injector or InputInjector()

    def copy(self, text: str) -> InputActionResult:
        try:
            self.injector.copy(text)
        except RuntimeError as exc:
            return InputActionResult(False, "", user_error_message(exc))
        return InputActionResult(True, "已复制到剪贴板")

    def paste(self, text: str) -> InputActionResult:
        try:
            self.injector.paste(text)
        except RuntimeError as exc:
            return InputActionResult(False, "", user_error_message(exc))
        return InputActionResult(True, "已插入到当前输入位置")

    def insert_preview(self, text: str, fallback: str = "") -> InputActionResult:
        value = text.strip() or fallback.strip()
        if not value:
            return InputActionResult(False, "", "没有可插入的预览文本")
        try:
            self.injector.paste(value)
        except RuntimeError as exc:
            return InputActionResult(False, "", user_error_message(exc))
        return InputActionResult(True, "预览文本已插入")
