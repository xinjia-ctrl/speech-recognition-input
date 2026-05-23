from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.text_tools import redact_secret, tidy_text, to_simplified_chinese


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    elapsed_seconds: float
    model_name: str
    error: str = ""


class AsrEngine:
    def __init__(
        self,
        provider: str = "local",
        model_size: str = "base",
        model_path: str = "",
        language: str = "zh",
        compute_type: str = "int8",
        initial_prompt: str = "请使用简体中文输出，保留自然的中文标点。",
        api_base_url: str = "",
        api_key: str = "",
        api_model: str = "",
        api_timeout_seconds: int = 60,
    ) -> None:
        self.provider = provider
        self.model_size = model_size
        self.model_path = model_path
        self.language = language
        self.compute_type = compute_type
        self.initial_prompt = initial_prompt
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.api_model = api_model
        self.api_timeout_seconds = api_timeout_seconds
        self._model = None

    @property
    def model_name(self) -> str:
        if self.provider == "api":
            return self.api_model or "api"
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

    def transcribe(
        self,
        audio_path: str,
        on_partial: Callable[[str], None] | None = None,
    ) -> TranscriptionResult:
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
            if self.provider == "api":
                return self._transcribe_with_api(path, started_at)
            if self.provider != "local":
                raise RuntimeError(f"不支持的语音识别模式：{self.provider}")
            return self._transcribe_with_local_model(path, started_at, on_partial)
        except Exception as exc:
            elapsed = time.perf_counter() - started_at
            return TranscriptionResult("", elapsed, self.model_name, redact_secret(str(exc)))

    def _transcribe_with_local_model(
        self,
        path: Path,
        started_at: float,
        on_partial: Callable[[str], None] | None = None,
    ) -> TranscriptionResult:
        model = self._load_model()
        segments, _info = model.transcribe(
            str(path),
            language=self.language,
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            initial_prompt=self.initial_prompt,
        )
        pieces = []
        for segment in segments:
            pieces.append(segment.text)
            partial_text = to_simplified_chinese(tidy_text("".join(pieces)))
            if on_partial is not None and partial_text:
                on_partial(partial_text)

        text = to_simplified_chinese(tidy_text("".join(pieces)))
        elapsed = time.perf_counter() - started_at
        return TranscriptionResult(text, elapsed, self.model_name)

    def _transcribe_with_api(self, path: Path, started_at: float) -> TranscriptionResult:
        if not self.api_base_url:
            raise RuntimeError("未配置云端 ASR API 地址")

        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("缺少 requests，请先安装依赖：pip install -r requirements.txt") from exc

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = {
            "language": self.language,
            "prompt": self.initial_prompt,
        }
        if self.api_model:
            data["model"] = self.api_model

        with path.open("rb") as audio_file:
            response = requests.post(
                self.api_base_url,
                headers=headers,
                data=data,
                files={"file": (path.name, audio_file, "audio/wav")},
                timeout=self.api_timeout_seconds,
            )
        response.raise_for_status()

        payload = response.json()
        text = self._extract_text_from_api_payload(payload)
        if not text:
            raise RuntimeError("云端 ASR API 响应中没有可用的 text 字段")

        text = to_simplified_chinese(tidy_text(text))
        elapsed = time.perf_counter() - started_at
        return TranscriptionResult(text, elapsed, self.model_name)

    @staticmethod
    def _extract_text_from_api_payload(payload: dict[str, Any]) -> str:
        for key in ("text", "transcript", "transcription"):
            value = payload.get(key)
            if isinstance(value, str):
                return value

        for key in ("data", "result"):
            value = payload.get(key)
            if isinstance(value, dict):
                nested = AsrEngine._extract_text_from_api_payload(value)
                if nested:
                    return nested

        return ""
