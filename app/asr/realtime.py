from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from array import array
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.errors import ConfigurationError, DependencyMissingError, ErrorKind, ExternalServiceError, user_error_message
from app.text_tools import (
    filter_text_by_language,
    tidy_text,
    to_simplified_chinese,
)


@dataclass(slots=True)
class RealtimeAsrConfig:
    websocket_url: str
    api_key: str = ""
    model: str = ""
    language: str = "zh"
    sample_rate: int = 16000
    channels: int = 1
    chunk_ms: int = 200
    final_wait_seconds: float = 1.5


class WebSocketRealtimeAsrClient:
    def __init__(self, config: RealtimeAsrConfig) -> None:
        self.config = config
        self._stop_capture_event = threading.Event()
        self._close_receiver_event = threading.Event()

    def stop(self) -> None:
        self._stop_capture_event.set()

    def run(
        self,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_error: Callable[[str], None],
        on_level: Callable[[float], None] | None = None,
    ) -> None:
        if not self.config.websocket_url:
            on_error(user_error_message(ConfigurationError("未配置 WebSocket 实时识别地址")))
            return

        try:
            import sounddevice as sd
            import websocket
        except ImportError:
            on_error(
                user_error_message(
                    DependencyMissingError("websocket-client", "pip install -r requirements-websocket.txt")
                )
            )
            return

        if self._is_dashscope_url(self.config.websocket_url):
            self._run_dashscope(websocket, sd, on_partial, on_final, on_error, on_level)
            return

        self._run_generic(websocket, sd, on_partial, on_final, on_error, on_level)

    def _run_generic(
        self,
        websocket,
        sd,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_error: Callable[[str], None],
        on_level: Callable[[float], None] | None = None,
    ) -> None:
        audio_queue: queue.Queue[bytes] = queue.Queue()
        ws = None
        receiver_thread = None
        final_texts: list[str] = []

        def callback(indata, frames, time_info, status) -> None:
            if status:
                return
            chunk = bytes(indata)
            audio_queue.put(chunk)
            self._emit_pcm_level(chunk, on_level)

        def receiver() -> None:
            while not self._close_receiver_event.is_set():
                try:
                    message = ws.recv()
                except Exception:
                    break

                text, is_final = self._parse_message(message)
                text = self._normalize_text(text)
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
                while not self._stop_capture_event.is_set():
                    try:
                        chunk = audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    ws.send_binary(chunk)

            ws.send(json.dumps({"type": "end"}, ensure_ascii=False))
            time.sleep(min(max(self.config.final_wait_seconds, 0.1), 3.0))
        except Exception as exc:
            on_error(user_error_message(exc))
        finally:
            self._stop_capture_event.set()
            self._close_receiver_event.set()
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass
            if receiver_thread is not None:
                receiver_thread.join(timeout=1)

    def _run_dashscope(
        self,
        websocket,
        sd,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_error: Callable[[str], None],
        on_level: Callable[[float], None] | None = None,
    ) -> None:
        audio_queue: queue.Queue[bytes] = queue.Queue()
        ws = None
        receiver_thread = None
        task_started = threading.Event()
        task_done = threading.Event()
        task_id = str(uuid.uuid4())
        final_texts: list[str] = []

        def callback(indata, frames, time_info, status) -> None:
            if status:
                return
            chunk = bytes(indata)
            audio_queue.put(chunk)
            self._emit_pcm_level(chunk, on_level)

        def receiver() -> None:
            while not self._close_receiver_event.is_set():
                try:
                    message = ws.recv()
                except Exception:
                    break

                event, text, is_final, error = self._parse_dashscope_message(message)
                text = self._normalize_text(text)
                if event == "task-started":
                    task_started.set()
                    continue
                if event == "task-finished":
                    task_done.set()
                    break
                if event == "task-failed":
                    on_error(
                        error
                        or user_error_message(
                            ExternalServiceError("百炼实时识别任务失败", kind=ErrorKind.REALTIME_ASR)
                        )
                    )
                    task_done.set()
                    break
                if event != "result-generated" or not text:
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
            headers.append("X-DashScope-DataInspection: enable")

            ws = websocket.create_connection(
                self.config.websocket_url,
                header=headers,
                timeout=10,
            )
            ws.send(
                json.dumps(
                    {
                        "header": {
                            "action": "run-task",
                            "task_id": task_id,
                            "streaming": "duplex",
                        },
                        "payload": {
                            "task_group": "audio",
                            "task": "asr",
                            "function": "recognition",
                            "model": self.config.model or "paraformer-realtime-v2",
                            "parameters": {
                                "format": "pcm",
                                "sample_rate": self.config.sample_rate,
                                "language_hints": [self.config.language],
                                "disfluency_removal_enabled": False,
                                "semantic_punctuation_enabled": True,
                            },
                            "input": {},
                        },
                    },
                    ensure_ascii=False,
                )
            )

            receiver_thread = threading.Thread(target=receiver, daemon=True)
            receiver_thread.start()
            if not task_started.wait(timeout=10):
                raise ExternalServiceError(
                    "等待百炼 task-started 超时，请检查 WebSocket 地址、Key 和模型名",
                    kind=ErrorKind.REALTIME_ASR,
                )

            blocksize = max(1, int(self.config.sample_rate * self.config.chunk_ms / 1000))
            with sd.RawInputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype="int16",
                blocksize=blocksize,
                callback=callback,
            ):
                while not self._stop_capture_event.is_set():
                    try:
                        chunk = audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    ws.send_binary(chunk)

            ws.send(
                json.dumps(
                    {
                        "header": {
                            "action": "finish-task",
                            "task_id": task_id,
                            "streaming": "duplex",
                        },
                        "payload": {"input": {}},
                    },
                    ensure_ascii=False,
                )
            )
            task_done.wait(timeout=max(self.config.final_wait_seconds, 0.1))
        except Exception as exc:
            on_error(user_error_message(exc))
        finally:
            self._stop_capture_event.set()
            self._close_receiver_event.set()
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass
            if receiver_thread is not None:
                receiver_thread.join(timeout=1)

    @staticmethod
    def _is_dashscope_url(url: str) -> bool:
        return "dashscope" in url.lower() or "aliyuncs.com/api-ws" in url.lower()

    @staticmethod
    def _emit_pcm_level(chunk: bytes, on_level: Callable[[float], None] | None) -> None:
        if on_level is None or not chunk:
            return
        try:
            samples = array("h")
            samples.frombytes(chunk)
            if not samples:
                return
            rms = (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
            on_level(min(max(rms / 4096, 0.0), 1.0))
        except Exception:
            pass

    def _normalize_text(self, text: str) -> str:
        return normalize_realtime_text(text, self.config.language)

    @staticmethod
    def _parse_dashscope_message(message: str | bytes) -> tuple[str, str, bool, str]:
        if isinstance(message, bytes):
            return "", "", False, ""

        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return "", "", False, ""

        header = payload.get("header") or {}
        body = payload.get("payload") or {}
        event = header.get("event", "")
        if event == "task-failed":
            error = body.get("message") or body.get("error") or header.get("error_message") or ""
            return event, "", False, user_error_message(str(error))

        output = body.get("output") or {}
        sentence = output.get("sentence") or {}
        text = sentence.get("text", "")
        is_final = bool(sentence.get("sentence_end") or sentence.get("end_time") is not None)
        return event, tidy_text(text), is_final, ""

    @staticmethod
    def _parse_message(message: str | bytes) -> tuple[str, bool]:
        if isinstance(message, bytes):
            return "", False

        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return tidy_text(message), True

        text = WebSocketRealtimeAsrClient._extract_text(payload)
        if not text:
            return "", False

        is_final = bool(
            payload.get("is_final")
            or payload.get("final")
            or payload.get("completed")
            or payload.get("type") in {"final", "completed", "end"}
        )
        return tidy_text(text), is_final

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


def normalize_realtime_text(text: str, language: str = "zh") -> str:
    filtered = filter_text_by_language(text, language)
    if language == "zh":
        return to_simplified_chinese(tidy_text(filtered))
    return tidy_text(filtered)
