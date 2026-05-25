from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.text_translate import translate_text_with_api


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
        except RuntimeError as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(translated)
