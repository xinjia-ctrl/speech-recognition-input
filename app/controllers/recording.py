from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.audio import Recorder
from app.asr import is_no_speech_message
from app.errors import ErrorKind, user_error_message


@dataclass(slots=True)
class RecordingActionResult:
    ok: bool
    audio_path: str = ""
    error: str = ""
    is_no_speech: bool = False


class RecordingController:
    def __init__(self, sample_rate: int, recorder: Recorder | None = None) -> None:
        self.recorder = recorder or Recorder(sample_rate=sample_rate)

    @property
    def is_recording(self) -> bool:
        return self.recorder.is_recording

    def start(self, on_level: Callable[[float], None] | None = None) -> RecordingActionResult:
        try:
            self.recorder.start(on_level=on_level)
        except Exception as exc:
            message = user_error_message(exc)
            is_no_speech = getattr(exc, "kind", None) == ErrorKind.NO_SPEECH or is_no_speech_message(message)
            return RecordingActionResult(False, error=message, is_no_speech=is_no_speech)
        return RecordingActionResult(True)

    def stop(self) -> RecordingActionResult:
        try:
            audio_path = self.recorder.stop()
        except Exception as exc:
            message = user_error_message(exc)
            is_no_speech = getattr(exc, "kind", None) == ErrorKind.NO_SPEECH or is_no_speech_message(message)
            return RecordingActionResult(False, error=message, is_no_speech=is_no_speech)
        return RecordingActionResult(True, audio_path=audio_path)
