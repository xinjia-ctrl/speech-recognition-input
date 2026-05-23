from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from app.text_tools import tidy_text


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    elapsed_seconds: float
    model_name: str
    error: str = ""


class AsrEngine:
    def __init__(
        self,
        model_size: str = "base",
        model_path: str = "",
        language: str = "zh",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.model_path = model_path
        self.language = language
        self.compute_type = compute_type
        self._model = None

    @property
    def model_name(self) -> str:
        return self.model_path or self.model_size

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("缺少 faster-whisper，请先安装依赖：pip install -r requirements.txt") from exc

        model_id = self.model_path or self.model_size
        self._model = WhisperModel(model_id, device="cpu", compute_type=self.compute_type)
        return self._model

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        started_at = time.perf_counter()
        path = Path(audio_path)
        if not path.exists():
            return TranscriptionResult(
                text="",
                elapsed_seconds=0,
                model_name=self.model_name,
                error=f"音频文件不存在：{path}",
            )

        try:
            model = self._load_model()
            segments, _info = model.transcribe(
                str(path),
                language=self.language,
                vad_filter=True,
            )
            text = tidy_text("".join(segment.text for segment in segments))
            elapsed = time.perf_counter() - started_at
            return TranscriptionResult(text, elapsed, self.model_name)
        except Exception as exc:
            elapsed = time.perf_counter() - started_at
            return TranscriptionResult("", elapsed, self.model_name, str(exc))
