from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.asr import AsrStreamEvent, TranscriptionResult, UnifiedAsrEngine
from app.controllers.recording import RecordingController
from app.controllers.transcription import RealtimeWebSocketWorker, TranscribeWorker


class RecognitionSessionController(QObject):
    audio_level = Signal(float)
    recording_started = Signal()
    recording_failed = Signal(object)
    recording_stopped = Signal(str)
    file_transcription_started = Signal(str)
    file_partial = Signal(str)
    file_fallback = Signal(str)
    file_finished = Signal(object)
    realtime_started = Signal()
    realtime_stopping = Signal()
    realtime_partial = Signal(str)
    realtime_final = Signal(str)
    realtime_error = Signal(str)
    realtime_finished = Signal()

    def __init__(self, engine: UnifiedAsrEngine, sample_rate: int) -> None:
        super().__init__()
        self.engine = engine
        self.recording_controller = RecordingController(sample_rate=sample_rate)
        self.file_worker: TranscribeWorker | None = None
        self.realtime_worker: RealtimeWebSocketWorker | None = None
        self.realtime_failed = False

    @property
    def is_recording(self) -> bool:
        return self.recording_controller.is_recording

    @property
    def is_file_transcribing(self) -> bool:
        return self.file_worker is not None and self.file_worker.isRunning()

    @property
    def is_realtime_running(self) -> bool:
        return self.realtime_worker is not None and self.realtime_worker.isRunning()

    def set_engine(self, engine: UnifiedAsrEngine) -> None:
        self.engine = engine

    def start_recording(self) -> None:
        result = self.recording_controller.start(on_level=self.audio_level.emit)
        if not result.ok:
            self.recording_failed.emit(result)
            return
        self.recording_started.emit()

    def stop_recording(self) -> None:
        result = self.recording_controller.stop()
        if not result.ok:
            self.recording_failed.emit(result)
            return
        self.recording_stopped.emit(result.audio_path)
        self.start_file_transcription(result.audio_path)

    def start_file_transcription(self, audio_path: str) -> None:
        self.file_transcription_started.emit(self.engine.model_name)
        self.file_worker = TranscribeWorker(self.engine, audio_path)
        self.file_worker.event.connect(self._handle_file_event)
        self.file_worker.finished.connect(self._handle_file_finished)
        self.file_worker.start()

    def start_realtime(self) -> None:
        self.realtime_failed = False
        self.realtime_worker = RealtimeWebSocketWorker(self.engine)
        self.realtime_worker.event.connect(self._handle_realtime_event)
        self.realtime_worker.finished.connect(self._handle_realtime_finished)
        self.realtime_worker.start()
        self.realtime_started.emit()

    def stop_realtime(self) -> None:
        if self.realtime_worker is not None:
            self.realtime_worker.stop()
        self.realtime_stopping.emit()

    def stop_all(self) -> None:
        if self.realtime_worker is not None and self.realtime_worker.isRunning():
            self.realtime_worker.stop()

    def _handle_file_event(self, event: AsrStreamEvent) -> None:
        if event.kind == "partial":
            self.file_partial.emit(event.text)
        elif event.kind == "fallback":
            self.file_fallback.emit(event.error)

    def _handle_file_finished(self, result: TranscriptionResult) -> None:
        self.file_worker = None
        self.file_finished.emit(result)

    def _handle_realtime_event(self, event: AsrStreamEvent) -> None:
        if event.kind == "partial":
            self.realtime_partial.emit(event.text)
        elif event.kind == "final":
            self.realtime_final.emit(event.text)
        elif event.kind == "error":
            self.realtime_failed = True
            self.realtime_error.emit(event.error)
        elif event.kind == "level":
            self.audio_level.emit(event.level)

    def _handle_realtime_finished(self) -> None:
        self.realtime_worker = None
        self.realtime_finished.emit()
