from __future__ import annotations

import queue
import wave
from collections.abc import Callable
from pathlib import Path


class RecordingError(RuntimeError):
    pass


class Recorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        output_dir: Path | str = Path("data/recordings"),
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.output_dir = Path(output_dir)
        self._stream = None
        self._chunks: queue.Queue[object] = queue.Queue()
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, on_level: Callable[[float], None] | None = None) -> None:
        if self._recording:
            raise RecordingError("录音已经在进行中")

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RecordingError("缺少 sounddevice，请先安装依赖：pip install -r requirements.txt") from exc

        self._chunks = queue.Queue()

        def callback(indata, frames, time_info, status) -> None:
            if status:
                self._chunks.put(status)
            self._chunks.put(indata.copy())
            if on_level is not None:
                try:
                    import numpy as np

                    level = float(np.sqrt(np.mean(np.square(indata))))
                    on_level(min(max(level * 8, 0.0), 1.0))
                except Exception:
                    pass

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=callback,
            )
            self._stream.start()
        except Exception as exc:
            raise RecordingError(f"无法启动麦克风录音：{exc}") from exc

        self._recording = True

    def stop(self, filename: str = "last_recording.wav") -> str:
        if not self._recording:
            raise RecordingError("当前没有正在进行的录音")

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._recording = False

        try:
            import numpy as np
        except ImportError as exc:
            raise RecordingError("缺少 numpy，请先安装依赖：pip install -r requirements.txt") from exc

        chunks = []
        while not self._chunks.empty():
            item = self._chunks.get()
            if hasattr(item, "shape"):
                chunks.append(item)

        if not chunks:
            raise RecordingError("没有采集到有效音频，请检查麦克风权限")

        audio = np.concatenate(chunks, axis=0)
        pcm = np.clip(audio, -1.0, 1.0)
        pcm = (pcm * 32767).astype(np.int16)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm.tobytes())

        return str(path)
