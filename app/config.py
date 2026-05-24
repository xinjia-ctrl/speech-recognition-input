from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("config/settings.json")


@dataclass(slots=True)
class Settings:
    asr_provider: str = "local"
    model_size: str = "base"
    model_path: str = ""
    language: str = "zh"
    api_base_url: str = ""
    api_key: str = ""
    api_model: str = ""
    local_beam_size: int = 1
    websocket_url: str = ""
    websocket_api_key: str = ""
    websocket_model: str = ""
    realtime_chunk_ms: int = 200
    websocket_final_wait_ms: int = 1500
    hotkey: str = "ctrl+alt+space"
    auto_insert: bool = False
    preview_before_insert: bool = True
    postprocess_enabled: bool = True
    postprocess_mode: str = "chat"
    dictionary_correction_enabled: bool = True
    ai_polish_enabled: bool = False
    ai_polish_api_base_url: str = ""
    ai_polish_api_key: str = ""
    ai_polish_model: str = ""
    translation_api_base_url: str = ""
    translation_api_key: str = ""
    translation_model: str = ""
    history_limit: int = 20
    sample_rate: int = 16000


class SettingsStore:
    def __init__(self, path: Path | str = DEFAULT_CONFIG_PATH) -> None:
        self.path = Path(path)

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        allowed_fields = {field.name for field in Settings.__dataclass_fields__.values()}
        values: dict[str, Any] = {
            key: value for key, value in raw.items() if key in allowed_fields
        }
        return Settings(**values)

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
