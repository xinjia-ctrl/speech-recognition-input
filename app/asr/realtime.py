from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.text_tools import redact_secret, tidy_text, to_simplified_chinese


@dataclass(slots=True)
class RealtimeAsrConfig:
    websocket_url: str
    api_key: str = ""
    model: str = ""
    language: str = "zh"
    sample_rate: int = 16000
    channels: int = 1
    chunk_ms: int = 200


class WebSocketRealtimeAsrClient:
    def __init__(self, config: RealtimeAsrConfig) -> None:
        self.config = config
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(
        self,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        if not self.config.websocket_url:
            on_error("未配置 WebSocket 实时识别地址")
            return

        try:
            import sounddevice as sd
            import websocket
        except ImportError as exc:
            on_error(f"缺少实时识别依赖，请先安装：pip install -r requirements.txt；{exc}")
            return

        audio_queue: queue.Queue[bytes] = queue.Queue()
        ws = None
        receiver_thread = None
        final_texts: list[str] = []

        def callback(indata, frames, time_info, status) -> None:
            if status:
                return
            audio_queue.put(bytes(indata))

        def receiver() -> None:
            while not self._stop_event.is_set():
                try:
                    message = ws.recv()
                except Exception:
                    break

                text, is_final = self._parse_message(message)
                if not text:
                    continue

                if is_final:
                    final_texts.append(text)
                    on_final(tidy_text("".join(final_texts)))
                else:
                    on_partial(tidy_text("".join(final_texts) + text))

        try:
            headers = []
            if self.config.api_key:
                headers.append(f"Authorization: Bearer {self.config.api_key}")

            ws = websocket.create_connection(
                self.config.websocket_url,
                header=headers,
                timeout=10,
            )
            ws.send(
                json.dumps(
                    {
                        "type": "start",
                        "model": self.config.model,
                        "language": self.config.language,
                        "sample_rate": self.config.sample_rate,
                        "format": "pcm_s16le",
                        "channels": self.config.channels,
                    },
                    ensure_ascii=False,
                )
            )

            receiver_thread = threading.Thread(target=receiver, daemon=True)
            receiver_thread.start()

            blocksize = max(1, int(self.config.sample_rate * self.config.chunk_ms / 1000))
            with sd.RawInputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype="int16",
                blocksize=blocksize,
                callback=callback,
            ):
                while not self._stop_event.is_set():
                    try:
                        chunk = audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    ws.send_binary(chunk)

            ws.send(json.dumps({"type": "end"}, ensure_ascii=False))
            time.sleep(0.3)
        except Exception as exc:
            on_error(redact_secret(str(exc)))
        finally:
            self._stop_event.set()
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass
            if receiver_thread is not None:
                receiver_thread.join(timeout=1)

    @staticmethod
    def _parse_message(message: str | bytes) -> tuple[str, bool]:
        if isinstance(message, bytes):
            return "", False

        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return to_simplified_chinese(tidy_text(message)), True

        text = WebSocketRealtimeAsrClient._extract_text(payload)
        if not text:
            return "", False

        is_final = bool(
            payload.get("is_final")
            or payload.get("final")
            or payload.get("completed")
            or payload.get("type") in {"final", "completed", "end"}
        )
        return to_simplified_chinese(text), is_final

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        for key in ("text", "transcript", "transcription", "partial"):
            value = payload.get(key)
            if isinstance(value, str):
                return value

        for key in ("data", "result"):
            value = payload.get(key)
            if isinstance(value, dict):
                nested = WebSocketRealtimeAsrClient._extract_text(value)
                if nested:
                    return nested

        return ""
