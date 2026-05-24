from __future__ import annotations

import re
from typing import Any

from app.text_tools import redact_secret, tidy_text, to_simplified_chinese


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


def translate_text_with_api(
    text: str,
    source_language: str,
    api_base_url: str,
    api_key: str,
    model: str,
    timeout_seconds: int = 30,
) -> str:
    if not api_base_url:
        raise RuntimeError("未配置翻译 API 地址")
    if not api_key:
        raise RuntimeError("未配置翻译 API Key")

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("缺少 requests，请先安装依赖：pip install -r requirements.txt") from exc

    target_language = "中文" if source_language == "en" else "英文"
    source_language_label = "英文" if source_language == "en" else "中文"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"你是专业翻译助手。请把用户输入的{source_language_label}翻译为{target_language}，"
                    "只输出译文，不要解释，不要添加引号。"
                ),
            },
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
    }
    if not model:
        payload.pop("model")

    try:
        response = requests.post(
            api_base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        translated = _extract_translation_text(response.json())
    except Exception as exc:
        raise RuntimeError(redact_secret(str(exc))) from exc

    if not translated:
        raise RuntimeError("翻译 API 响应中没有可用文本")
    return _normalize_translation_result(translated, source_language)


def translation_button_label(language: str) -> str:
    return "英翻中" if language == "en" else "中翻英"


def _extract_translation_text(payload: dict[str, Any]) -> str:
    value = payload.get("text")
    if isinstance(value, str):
        return value

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]

    for key in ("data", "result", "output"):
        value = payload.get(key)
        if isinstance(value, dict):
            nested = _extract_translation_text(value)
            if nested:
                return nested
        if isinstance(value, str):
            return value

    return ""


def _normalize_translation_result(text: str, source_language: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip().strip('"“”')
    if source_language == "en":
        return tidy_text(to_simplified_chinese(cleaned))
    return cleaned


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
