from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable


DEFAULT_HISTORY_PATH = Path("data/history.json")


@dataclass(slots=True)
class HistoryItem:
    text: str
    created_at: str


@runtime_checkable
class HistoryRepository(Protocol):
    limit: int

    def list(self) -> list[HistoryItem]: ...

    def add(self, text: str) -> list[HistoryItem]: ...

    def clear(self) -> None: ...


class JsonHistoryRepository:
    def __init__(self, path: Path | str = DEFAULT_HISTORY_PATH, limit: int = 20) -> None:
        self.path = Path(path)
        self.limit = max(1, limit)

    def list(self) -> list[HistoryItem]:
        if not self.path.exists():
            return []

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return []
        if not isinstance(raw, list):
            return []

        items: list[HistoryItem] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            created_at = item.get("created_at")
            if not isinstance(text, str) or not text.strip():
                continue
            if not isinstance(created_at, str):
                created_at = ""
            items.append(HistoryItem(text=text, created_at=created_at))
        return items

    def add(self, text: str) -> list[HistoryItem]:
        value = text.strip()
        if not value:
            return self.list()

        items = self.list()
        items.insert(
            0,
            HistoryItem(
                text=value,
                created_at=datetime.now().isoformat(timespec="seconds"),
            ),
        )
        items = items[: self.limit]

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return items

    def clear(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("[]", encoding="utf-8")


class HistoryStore(JsonHistoryRepository):
    """兼容旧调用名；新代码优先依赖 HistoryRepository 接口。"""
