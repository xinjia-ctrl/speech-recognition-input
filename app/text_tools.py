from __future__ import annotations

import re


def tidy_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace(" ,", "，").replace(" .", "。")
    cleaned = cleaned.replace(",", "，").replace(".", "。")
    return cleaned
