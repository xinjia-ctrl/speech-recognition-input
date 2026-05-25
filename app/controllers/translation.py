from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal

from app.errors import user_error_message
from app.text_translate import translate_text_with_api


@dataclass(slots=True)
class TranslationRequest:
    text: str
    source_language: str
    api_base_url: str
    api_key: str
    model: str


class TranslationWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        text: str,
        source_language: str,
        api_base_url: str,
        api_key: str,
        model: str,
    ) -> None:
        super().__init__()
        self.text = text
        self.source_language = source_language
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.model = model

    def run(self) -> None:
        try:
            translated = translate_text_with_api(
                self.text,
                self.source_language,
                self.api_base_url,
                self.api_key,
                self.model,
            )
        except Exception as exc:
            self.error.emit(user_error_message(exc))
            return
        self.finished.emit(translated)


class TranslationController(QObject):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.worker: TranslationWorker | None = None

    def is_running(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def start(self, request: TranslationRequest) -> bool:
        if self.is_running():
            return False

        self.worker = TranslationWorker(
            request.text,
            request.source_language,
            request.api_base_url,
            request.api_key,
            request.model,
        )
        self.worker.finished.connect(self._handle_finished)
        self.worker.error.connect(self._handle_error)
        self.worker.start()
        return True

    def _handle_finished(self, translated: str) -> None:
        self.worker = None
        self.finished.emit(translated)

    def _handle_error(self, message: str) -> None:
        self.worker = None
        self.error.emit(message)
