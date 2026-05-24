from __future__ import annotations

import re

from app.text_tools import tidy_text, to_simplified_chinese


FILLER_WORDS = (
    "呃",
    "嗯",
    "啊",
    "额",
    "那个",
    "这个",
    "就是",
    "然后然后",
)

QUESTION_CUES = (
    "吗",
    "呢",
    "是不是",
    "为什么",
    "怎么",
    "如何",
    "能不能",
    "可不可以",
)

EXCLAMATION_CUES = (
    "太好了",
    "完美",
    "厉害",
    "救命",
    "糟糕",
)

CODE_REPLACEMENTS = (
    (re.compile(r"\bi\s*f\s*语句\b", re.IGNORECASE), "if :"),
    (re.compile(r"\bif\s*语句\b", re.IGNORECASE), "if :"),
    (re.compile(r"for\s*循环", re.IGNORECASE), "for :"),
    (re.compile(r"while\s*循环", re.IGNORECASE), "while :"),
    (re.compile(r"打印\s*([A-Za-z0-9_\-\u4e00-\u9fff ]+)"), r'print("\1")'),
)


def postprocess_text(text: str, mode: str = "chat", enabled: bool = True) -> str:
    if not enabled:
        return tidy_text(text)

    cleaned = to_simplified_chinese(tidy_text(text))
    cleaned = _remove_fillers(cleaned)
    cleaned = _collapse_repeated_words(cleaned)

    if mode == "code":
        cleaned = _apply_code_replacements(cleaned)
    elif mode == "document":
        cleaned = _normalize_document_style(cleaned)

    return _apply_sentence_punctuation(tidy_text(cleaned))


def _remove_fillers(text: str) -> str:
    cleaned = text
    for word in FILLER_WORDS:
        cleaned = cleaned.replace(word, "")
    return cleaned


def _collapse_repeated_words(text: str) -> str:
    return re.sub(r"([\u4e00-\u9fff]{1,4})\1+", r"\1", text)


def _apply_code_replacements(text: str) -> str:
    converted = text
    for pattern, replacement in CODE_REPLACEMENTS:
        converted = pattern.sub(replacement, converted)
    return converted


def _normalize_document_style(text: str) -> str:
    return text.replace("挺", "比较").replace("特别特别", "特别")


def _apply_sentence_punctuation(text: str) -> str:
    if not text:
        return ""
    if text[-1] in "。！？!?":
        return text
    if any(cue in text for cue in QUESTION_CUES):
        return f"{text}？"
    if any(cue in text for cue in EXCLAMATION_CUES):
        return f"{text}！"
    return f"{text}。"
