from __future__ import annotations

import re

from app.text_tools import tidy_text, to_simplified_chinese


ZH_TO_EN_PHRASES = {
    "你好": "hello",
    "谢谢": "thank you",
    "请帮我确认这个接口是否已经上线": "Please help me confirm whether this API has been released",
    "请帮我确认": "Please help me confirm",
    "这个接口": "this API",
    "是否已经上线": "whether it has been released",
    "已经上线": "has been released",
    "没有问题": "No problem",
    "稍后回复你": "I will reply to you later",
}

EN_TO_ZH_PHRASES = {
    "hello": "你好",
    "thank you": "谢谢",
    "no problem": "没有问题",
    "please help me confirm": "请帮我确认",
    "this api": "这个接口",
    "has been released": "已经上线",
    "i will reply to you later": "我稍后回复你",
}


def translate_text(text: str, source_language: str) -> str:
    cleaned = tidy_text(text)
    if source_language == "en":
        return _translate_en_to_zh(cleaned)
    return _translate_zh_to_en(to_simplified_chinese(cleaned))


def translation_button_label(language: str) -> str:
    return "英翻中" if language == "en" else "中翻英"


def _translate_zh_to_en(text: str) -> str:
    translated = text
    for source in sorted(ZH_TO_EN_PHRASES, key=len, reverse=True):
        translated = translated.replace(source, ZH_TO_EN_PHRASES[source])
    translated = translated.replace("？", "?").replace("。", ".").replace("！", "!")
    translated = re.sub(r"\s+", " ", translated).strip()
    return translated


def _translate_en_to_zh(text: str) -> str:
    translated = text.lower()
    for source in sorted(EN_TO_ZH_PHRASES, key=len, reverse=True):
        translated = translated.replace(source, EN_TO_ZH_PHRASES[source])
    translated = translated.replace("?", "？").replace(".", "。").replace("!", "！")
    return tidy_text(translated)
