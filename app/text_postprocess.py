from __future__ import annotations

from app.text_pipeline import process_text_pipeline


def postprocess_text(text: str, mode: str = "chat", enabled: bool = True) -> str:
    return process_text_pipeline(text, mode=mode, enabled=enabled)
