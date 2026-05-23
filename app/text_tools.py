from __future__ import annotations

import re


_SECRET_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
)

_BASIC_T2S_MAP = str.maketrans(
    {
        "語": "语",
        "音": "音",
        "輸": "输",
        "入": "入",
        "軟": "软",
        "體": "体",
        "開": "开",
        "發": "发",
        "測": "测",
        "試": "试",
        "識": "识",
        "別": "别",
        "結": "结",
        "構": "构",
        "設": "设",
        "置": "置",
        "歷": "历",
        "史": "史",
        "記": "记",
        "錄": "录",
        "臺": "台",
        "國": "国",
        "與": "与",
        "為": "为",
        "後": "后",
        "這": "这",
        "個": "个",
        "麼": "么",
        "嗎": "吗",
        "時": "时",
        "間": "间",
        "點": "点",
        "雲": "云",
        "數": "数",
        "據": "据",
        "學": "学",
        "習": "习",
        "應": "应",
        "用": "用",
        "場": "场",
        "景": "景",
        "簡": "简",
        "繁": "繁",
        "轉": "转",
    }
)

_BASIC_T2S_PHRASES = {
    "軟體": "软件",
}

_JAPANESE_KANA_PATTERN = re.compile(r"[\u3040-\u30ff]")
_KOREAN_HANGUL_PATTERN = re.compile(r"[\uac00-\ud7af]")
_LATIN_PATTERN = re.compile(r"[A-Za-z]+")
_CJK_PATTERN = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]+")


def redact_secret(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("***", redacted)
    return redacted


def to_simplified_chinese(text: str) -> str:
    try:
        from opencc import OpenCC
    except ImportError:
        converted = text
        for source, target in _BASIC_T2S_PHRASES.items():
            converted = converted.replace(source, target)
        return converted.translate(_BASIC_T2S_MAP)

    converted = OpenCC("t2s").convert(text)
    for source, target in {"软体": "软件"}.items():
        converted = converted.replace(source, target)
    return converted


def remove_cjk_false_positive_text(text: str) -> str:
    return _KOREAN_HANGUL_PATTERN.sub("", _JAPANESE_KANA_PATTERN.sub("", text))


def filter_text_by_language(text: str, language: str) -> str:
    if language == "en":
        return _CJK_PATTERN.sub("", text)
    if language == "zh":
        return _LATIN_PATTERN.sub("", remove_cjk_false_positive_text(text))
    return remove_cjk_false_positive_text(text)


def tidy_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace(" ,", "，").replace(" .", "。")
    cleaned = cleaned.replace(",", "，").replace(".", "。")
    return cleaned
