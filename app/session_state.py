from __future__ import annotations

import time
from dataclasses import dataclass

from app.text_tools import redact_secret


@dataclass(slots=True)
class SessionDiagnostics:
    started_at: float | None = None
    first_text_at: float | None = None
    stop_at: float | None = None
    finished_at: float | None = None
    last_error: str = ""

    def start(self) -> None:
        now = time.perf_counter()
        self.started_at = now
        self.first_text_at = None
        self.stop_at = None
        self.finished_at = None
        self.last_error = ""

    def mark_first_text(self) -> None:
        if self.started_at is not None and self.first_text_at is None:
            self.first_text_at = time.perf_counter()

    def mark_stop(self) -> None:
        if self.started_at is not None and self.stop_at is None:
            self.stop_at = time.perf_counter()

    def mark_finish(self) -> None:
        if self.started_at is not None:
            self.finished_at = time.perf_counter()

    def set_error(self, message: str) -> None:
        self.last_error = redact_secret(message)

    @property
    def first_text_latency(self) -> float | None:
        if self.started_at is None or self.first_text_at is None:
            return None
        return self.first_text_at - self.started_at

    @property
    def tail_latency(self) -> float | None:
        if self.stop_at is None or self.finished_at is None:
            return None
        return self.finished_at - self.stop_at

    @property
    def total_elapsed(self) -> float | None:
        if self.started_at is None or self.finished_at is None:
            return None
        return self.finished_at - self.started_at
