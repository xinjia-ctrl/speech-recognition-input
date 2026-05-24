from __future__ import annotations

from collections.abc import Callable

from app.asr.engine import TranscriptionResult
from app.asr.providers import AsrProvider, AsrStreamEvent, WebSocketRealtimeProvider, build_asr_provider
from app.asr.realtime import RealtimeAsrConfig
from app.config import Settings


class UnifiedAsrEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = build_asr_provider(settings)

    @property
    def model_name(self) -> str:
        return self.provider.model_name

    def transcribe_file(
        self,
        audio_path: str,
        emit: Callable[[AsrStreamEvent], None],
    ) -> TranscriptionResult:
        return self.provider.transcribe_file(audio_path, emit)

    def run_realtime(self, emit: Callable[[AsrStreamEvent], None]) -> TranscriptionResult:
        return self.provider.run_realtime(emit)

    def stop_realtime(self) -> None:
        self.provider.stop()

    @staticmethod
    def _build_realtime_config(settings: Settings) -> RealtimeAsrConfig:
        return WebSocketRealtimeProvider.build_config(settings)

    @staticmethod
    def _build_provider(settings: Settings) -> AsrProvider:
        return build_asr_provider(settings)
