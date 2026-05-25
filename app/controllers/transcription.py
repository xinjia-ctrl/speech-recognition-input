from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.asr import UnifiedAsrEngine


class TranscribeWorker(QThread):
    event = Signal(object)
    finished = Signal(object)

    def __init__(self, engine: UnifiedAsrEngine, audio_path: str) -> None:
        super().__init__()
        self.engine = engine
        self.audio_path = audio_path

    def run(self) -> None:
        self.finished.emit(self.engine.transcribe_file(self.audio_path, self.event.emit))


class RealtimeWebSocketWorker(QThread):
    event = Signal(object)

    def __init__(self, engine: UnifiedAsrEngine) -> None:
        super().__init__()
        self.engine = engine

    def run(self) -> None:
        self.engine.run_realtime(self.event.emit)

    def stop(self) -> None:
        self.engine.stop_realtime()
