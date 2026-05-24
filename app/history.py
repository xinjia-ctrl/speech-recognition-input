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

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [HistoryItem(**item) for item in raw if item.get("text")]

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
