from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.asr.engine import AsrEngine, TranscriptionResult
from app.asr.realtime import RealtimeAsrConfig, WebSocketRealtimeAsrClient
from app.config import Settings


@dataclass(slots=True)
class AsrStreamEvent:
    kind: str
    text: str = ""
    error: str = ""
    level: float = 0.0
    result: TranscriptionResult | None = None


class UnifiedAsrEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.file_engine = self._build_file_engine(settings)
        self.realtime_client: WebSocketRealtimeAsrClient | None = None

    @property
    def model_name(self) -> str:
        if self.settings.asr_provider == "websocket":
            return self.settings.websocket_model or "websocket"
        return self.file_engine.model_name

    def transcribe_file(
        self,
        audio_path: str,
        emit: Callable[[AsrStreamEvent], None],
    ) -> TranscriptionResult:
        emit(AsrStreamEvent("started"))

        def emit_partial(text: str) -> None:
            emit(AsrStreamEvent("partial", text=text))

        result = self.file_engine.transcribe(audio_path, on_partial=emit_partial)
        if result.error:
            emit(AsrStreamEvent("error", error=result.error, result=result))
        else:
            emit(AsrStreamEvent("final", text=result.text, result=result))
        emit(AsrStreamEvent("finished", text=result.text, error=result.error, result=result))
        return result

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

        self.realtime_client = WebSocketRealtimeAsrClient(self._build_realtime_config(self.settings))
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

    def stop_realtime(self) -> None:
        if self.realtime_client is not None:
            self.realtime_client.stop()

    @staticmethod
    def _build_file_engine(settings: Settings) -> AsrEngine:
        return AsrEngine(
            provider=settings.asr_provider,
            model_size=settings.model_size,
            model_path=settings.model_path,
            language=settings.language,
            beam_size=settings.local_beam_size,
            api_base_url=settings.api_base_url,
            api_key=settings.api_key,
            api_model=settings.api_model,
        )

    @staticmethod
    def _build_realtime_config(settings: Settings) -> RealtimeAsrConfig:
        return RealtimeAsrConfig(
            websocket_url=settings.websocket_url,
            api_key=settings.websocket_api_key or settings.api_key,
            model=settings.websocket_model,
            language=settings.language,
            sample_rate=settings.sample_rate,
            chunk_ms=settings.realtime_chunk_ms,
            final_wait_seconds=settings.websocket_final_wait_ms / 1000,
        )
