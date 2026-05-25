from __future__ import annotations

from app.config import Settings
from app.session_state import SessionDiagnostics


ENGINE_SETTING_FIELDS = (
    "asr_provider",
    "model_size",
    "model_path",
    "language",
    "api_base_url",
    "api_key",
    "api_model",
    "fallback_to_local",
    "local_beam_size",
    "websocket_url",
    "websocket_api_key",
    "websocket_model",
    "realtime_chunk_ms",
    "websocket_final_wait_ms",
)


def provider_label(settings: Settings) -> str:
    if settings.asr_provider == "api":
        return "云端 API（本地兜底）" if settings.fallback_to_local else "云端 API"
    if settings.asr_provider == "websocket":
        return "WebSocket 实时识别"
    return "本地模型"


def language_label(settings: Settings) -> str:
    if settings.language == "en":
        return "English"
    return "中文"


def engine_settings_changed(old: Settings, new: Settings) -> bool:
    return any(getattr(old, field) != getattr(new, field) for field in ENGINE_SETTING_FIELDS)


def diagnostic_values(settings: Settings, diagnostics: SessionDiagnostics, state: str) -> dict[str, str]:
    return {
        "provider": provider_label(settings),
        "language": language_label(settings),
        "api_key": _configured(settings.api_key),
        "translation_key": _configured(settings.translation_api_key),
        "translation_url": _configured(settings.translation_api_base_url),
        "websocket_key": _configured(settings.websocket_api_key or settings.api_key),
        "websocket_url": _configured(settings.websocket_url),
        "state": state,
        "first_text_latency": _format_duration(diagnostics.first_text_latency),
        "tail_latency": _format_duration(diagnostics.tail_latency),
        "total_elapsed": _format_duration(diagnostics.total_elapsed),
        "last_error": diagnostics.last_error or "无",
    }


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    return f"{seconds * 1000:.0f} ms"


def _configured(value: str) -> str:
    return "已配置" if value.strip() else "未配置"
