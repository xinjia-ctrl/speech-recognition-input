from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.asr.engine import AsrEngine, TranscriptionResult
from app.asr.errors import is_no_speech_message
from app.asr.realtime import RealtimeAsrConfig, WebSocketRealtimeAsrClient
from app.config import Settings


@dataclass(slots=True)
class AsrStreamEvent:
    kind: str
    text: str = ""
    error: str = ""
    level: float = 0.0
    result: TranscriptionResult | None = None


class AsrProvider:
    name = "base"
    supports_file = False
    supports_realtime = False

    @property
    def model_name(self) -> str:
        return self.name

    def transcribe_file(
        self,
        audio_path: str,
        emit: Callable[[AsrStreamEvent], None],
    ) -> TranscriptionResult:
        result = TranscriptionResult("", 0, self.model_name, f"{self.name} 不支持文件识别")
        emit(AsrStreamEvent("error", error=result.error, result=result))
        emit(AsrStreamEvent("finished", error=result.error, result=result))
        return result

    def run_realtime(self, emit: Callable[[AsrStreamEvent], None]) -> TranscriptionResult:
        result = TranscriptionResult("", 0, self.model_name, f"{self.name} 不支持实时识别")
        emit(AsrStreamEvent("error", error=result.error, result=result))
        emit(AsrStreamEvent("finished", error=result.error, result=result))
        return result

    def stop(self) -> None:
        return


class FileAsrProvider(AsrProvider):
    supports_file = True

    def __init__(self, engine: AsrEngine) -> None:
        self.engine = engine

    @property
    def model_name(self) -> str:
        return self.engine.model_name

    def transcribe_file(
        self,
        audio_path: str,
        emit: Callable[[AsrStreamEvent], None],
    ) -> TranscriptionResult:
        emit(AsrStreamEvent("started"))

        def emit_partial(text: str) -> None:
            emit(AsrStreamEvent("partial", text=text))

        result = self.engine.transcribe(audio_path, on_partial=emit_partial)
        if result.error:
            emit(AsrStreamEvent("error", error=result.error, result=result))
        else:
            emit(AsrStreamEvent("final", text=result.text, result=result))
        emit(AsrStreamEvent("finished", text=result.text, error=result.error, result=result))
        return result


class LocalWhisperProvider(FileAsrProvider):
    name = "local"

    def __init__(self, settings: Settings) -> None:
        super().__init__(
            AsrEngine(
                provider="local",
                model_size=settings.model_size,
                model_path=settings.model_path,
                language=settings.language,
                beam_size=settings.local_beam_size,
            )
        )


class HttpAsrProvider(FileAsrProvider):
    name = "api"

    def __init__(self, settings: Settings) -> None:
        api_key = settings.api_key
        if "dashscope" in settings.api_base_url.lower() and settings.websocket_api_key:
            api_key = settings.websocket_api_key
        super().__init__(
            AsrEngine(
                provider="api",
                language=settings.language,
                api_base_url=settings.api_base_url,
                api_key=api_key,
                api_model=settings.api_model,
            )
        )


class FallbackAsrProvider(AsrProvider):
    name = "api_local_fallback"
    supports_file = True

    def __init__(self, primary: AsrProvider, fallback: AsrProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    @property
    def model_name(self) -> str:
        return f"{self.primary.model_name} -> {self.fallback.model_name}"

    def transcribe_file(
        self,
        audio_path: str,
        emit: Callable[[AsrStreamEvent], None],
    ) -> TranscriptionResult:
        primary_events: list[AsrStreamEvent] = []
        primary_result = self.primary.transcribe_file(audio_path, primary_events.append)
        if not primary_result.error or is_no_speech_message(primary_result.error):
            for event in primary_events:
                emit(event)
            return primary_result

        emit(
            AsrStreamEvent(
                "fallback",
                error=f"云端识别失败，正在切换本地模型：{primary_result.error}",
                result=primary_result,
            )
        )
        fallback_result = self.fallback.transcribe_file(audio_path, emit)
        elapsed = primary_result.elapsed_seconds + fallback_result.elapsed_seconds
        model_name = f"{primary_result.model_name} -> {fallback_result.model_name}"
        if fallback_result.error:
            return TranscriptionResult(
                text="",
                elapsed_seconds=elapsed,
                model_name=model_name,
                error=f"云端识别失败：{primary_result.error}；本地兜底失败：{fallback_result.error}",
            )
        return TranscriptionResult(
            text=fallback_result.text,
            elapsed_seconds=elapsed,
            model_name=model_name,
        )


class WebSocketRealtimeProvider(AsrProvider):
    name = "websocket"
    supports_realtime = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.realtime_client: WebSocketRealtimeAsrClient | None = None

    @property
    def model_name(self) -> str:
        return self.settings.websocket_model or "websocket"

    def run_realtime(self, emit: Callable[[AsrStreamEvent], None]) -> TranscriptionResult:
        started_at = time.perf_counter()
        last_text = ""
        last_error = ""
        emit(AsrStreamEvent("started"))

        def on_partial(text: str) -> None:
            nonlocal last_text
            last_text = text
            emit(AsrStreamEvent("partial", text=text))

        def on_final(text: str) -> None:
            nonlocal last_text
            last_text = text
            emit(AsrStreamEvent("final", text=text))

        def on_error(message: str) -> None:
            nonlocal last_error
            last_error = message
            emit(AsrStreamEvent("error", error=message))

        def on_level(level: float) -> None:
            emit(AsrStreamEvent("level", level=level))

        self.realtime_client = WebSocketRealtimeAsrClient(self.build_config(self.settings))
        self.realtime_client.run(
            on_partial=on_partial,
            on_final=on_final,
            on_error=on_error,
            on_level=on_level,
        )
        elapsed = time.perf_counter() - started_at
        result = TranscriptionResult(
            text=last_text,
            elapsed_seconds=elapsed,
            model_name=self.model_name,
            error=last_error,
        )
        emit(AsrStreamEvent("finished", text=last_text, error=last_error, result=result))
        self.realtime_client = None
        return result

    def stop(self) -> None:
        if self.realtime_client is not None:
            self.realtime_client.stop()

    @staticmethod
    def build_config(settings: Settings) -> RealtimeAsrConfig:
        return RealtimeAsrConfig(
            websocket_url=settings.websocket_url,
            api_key=settings.websocket_api_key or settings.api_key,
            model=settings.websocket_model,
            language=settings.language,
            sample_rate=settings.sample_rate,
            chunk_ms=settings.realtime_chunk_ms,
            final_wait_seconds=settings.websocket_final_wait_ms / 1000,
        )


def build_asr_provider(settings: Settings) -> AsrProvider:
    if settings.asr_provider == "api":
        api_provider = HttpAsrProvider(settings)
        if settings.fallback_to_local:
            return FallbackAsrProvider(api_provider, LocalWhisperProvider(settings))
        return api_provider
    if settings.asr_provider == "websocket":
        return WebSocketRealtimeProvider(settings)
    return LocalWhisperProvider(settings)
