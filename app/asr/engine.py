from __future__ import annotations

import time
import base64
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.errors import ConfigurationError, DependencyMissingError, ErrorKind, ExternalServiceError, user_error_message
from app.text_tools import tidy_text, to_simplified_chinese


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
        beam_size: int = 1,
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
        self.beam_size = beam_size
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
            raise DependencyMissingError("faster-whisper", "pip install -r requirements-local.txt") from exc

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
                raise ConfigurationError(f"不支持的语音识别模式：{self.provider}")
            return self._transcribe_with_local_model(path, started_at, on_partial)
        except Exception as exc:
            elapsed = time.perf_counter() - started_at
            return TranscriptionResult("", elapsed, self.model_name, user_error_message(exc))

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
            beam_size=self.beam_size,
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
            raise ConfigurationError("未配置云端 ASR API 地址")

        try:
            import requests
        except ImportError as exc:
            raise DependencyMissingError("requests", "pip install -r requirements-cloud.txt") from exc

        if self._is_dashscope_qwen_asr_endpoint(self.api_base_url):
            return self._transcribe_with_dashscope_qwen_asr(path, started_at, requests)

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
            raise ExternalServiceError("云端 ASR API 响应中没有可用的 text 字段", kind=ErrorKind.ASR)

        text = to_simplified_chinese(tidy_text(text))
        elapsed = time.perf_counter() - started_at
        return TranscriptionResult(text, elapsed, self.model_name)

    def _transcribe_with_dashscope_qwen_asr(
        self,
        path: Path,
        started_at: float,
        requests_module: Any,
    ) -> TranscriptionResult:
        if not self.api_model:
            raise ConfigurationError("未配置百炼 Qwen-ASR 模型名，建议使用 qwen3-asr-flash")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        audio_data = base64.b64encode(path.read_bytes()).decode("ascii")
        payload = {
            "model": self.api_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": f"data:audio/wav;base64,{audio_data}",
                            },
                        }
                    ],
                }
            ],
            "stream": False,
            "asr_options": {
                "language": self.language,
                "enable_itn": True,
            },
        }
        if self.initial_prompt:
            payload["messages"].insert(
                0,
                {
                    "role": "system",
                    "content": [{"type": "text", "text": self.initial_prompt}],
                },
            )

        response = requests_module.post(
            self._dashscope_qwen_asr_url(self.api_base_url),
            headers=headers,
            json=payload,
            timeout=self.api_timeout_seconds,
        )
        response.raise_for_status()

        text = self._extract_text_from_api_payload(response.json())
        if not text:
            raise ExternalServiceError("云端 ASR API 响应中没有可用文本", kind=ErrorKind.ASR)

        text = to_simplified_chinese(tidy_text(text))
        elapsed = time.perf_counter() - started_at
        return TranscriptionResult(text, elapsed, self.model_name)

    @staticmethod
    def _is_dashscope_qwen_asr_endpoint(url: str) -> bool:
        normalized = url.strip().lower()
        return "dashscope" in normalized and "compatible-mode/v1" in normalized

    @staticmethod
    def _dashscope_qwen_asr_url(url: str) -> str:
        normalized = url.strip().rstrip("/")
        if normalized.endswith("/audio/transcriptions"):
            return normalized[: -len("/audio/transcriptions")] + "/chat/completions"
        if normalized.endswith("/chat/completions"):
            return normalized
        if normalized.endswith("/compatible-mode/v1"):
            return f"{normalized}/chat/completions"
        return normalized

    @staticmethod
    def _extract_text_from_api_payload(payload: dict[str, Any]) -> str:
        for key in ("text", "transcript", "transcription"):
            value = payload.get(key)
            if isinstance(value, str):
                return value

        choices = payload.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content
                delta = choice.get("delta")
                if isinstance(delta, dict):
                    content = delta.get("content")
                    if isinstance(content, str):
                        return content

        for key in ("data", "result"):
            value = payload.get(key)
            if isinstance(value, dict):
                nested = AsrEngine._extract_text_from_api_payload(value)
                if nested:
                    return nested

        return ""
