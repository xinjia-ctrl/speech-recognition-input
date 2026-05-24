from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.text_tools import redact_secret, tidy_text, to_simplified_chinese


DEFAULT_CORRECTIONS = {
    "七牛": "七牛云",
    "七牛云云": "七牛云",
    "百练": "百炼",
    "百炼云": "百炼",
    "硅基流动": "硅基流动",
    "web socket": "WebSocket",
    "websocket": "WebSocket",
    "派 side": "PySide",
    "pyside": "PySide",
    "faster whisper": "faster-whisper",
    "open ai": "OpenAI",
}

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


@dataclass(slots=True)
class TextPipelineOptions:
    mode: str = "chat"
    enabled: bool = True
    dictionary_enabled: bool = True
    ai_polish_enabled: bool = False
    ai_api_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""


class TextPipelineStage:
    def process(self, text: str, options: TextPipelineOptions) -> str:
        return text


class DictionaryCorrectionStage(TextPipelineStage):
    def __init__(self, corrections: dict[str, str] | None = None) -> None:
        self.corrections = corrections or DEFAULT_CORRECTIONS

    def process(self, text: str, options: TextPipelineOptions) -> str:
        if not options.dictionary_enabled:
            return text

        corrected = text
        for source in sorted(self.corrections, key=len, reverse=True):
            corrected = re.sub(re.escape(source), self.corrections[source], corrected, flags=re.IGNORECASE)
        return corrected


class RuleCleanupStage(TextPipelineStage):
    def process(self, text: str, options: TextPipelineOptions) -> str:
        if not options.enabled:
            return tidy_text(text)

        cleaned = to_simplified_chinese(tidy_text(text))
        cleaned = self._remove_fillers(cleaned)
        cleaned = self._collapse_repeated_words(cleaned)

        if options.mode == "code":
            cleaned = self._apply_code_replacements(cleaned)
        elif options.mode == "document":
            cleaned = self._normalize_document_style(cleaned)

        return self._apply_sentence_punctuation(tidy_text(cleaned))

    @staticmethod
    def _remove_fillers(text: str) -> str:
        cleaned = text
        for word in FILLER_WORDS:
            cleaned = cleaned.replace(word, "")
        return cleaned

    @staticmethod
    def _collapse_repeated_words(text: str) -> str:
        return re.sub(r"([\u4e00-\u9fff]{1,4})\1+", r"\1", text)

    @staticmethod
    def _apply_code_replacements(text: str) -> str:
        converted = text
        for pattern, replacement in CODE_REPLACEMENTS:
            converted = pattern.sub(replacement, converted)
        return converted

    @staticmethod
    def _normalize_document_style(text: str) -> str:
        return text.replace("挺", "比较").replace("特别特别", "特别")

    @staticmethod
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


class AiPolishStage(TextPipelineStage):
    def process(self, text: str, options: TextPipelineOptions) -> str:
        if not options.ai_polish_enabled:
            return text
        return polish_text_with_api(
            text,
            mode=options.mode,
            api_base_url=options.ai_api_base_url,
            api_key=options.ai_api_key,
            model=options.ai_model,
        )


class TextProcessingPipeline:
    def __init__(self, stages: Iterable[TextPipelineStage] | None = None) -> None:
        self.stages = list(stages) if stages is not None else [
            DictionaryCorrectionStage(),
            RuleCleanupStage(),
            AiPolishStage(),
        ]

    def process(self, text: str, options: TextPipelineOptions) -> str:
        processed = text
        for stage in self.stages:
            processed = stage.process(processed, options)
        return processed


def process_text_pipeline(
    text: str,
    mode: str = "chat",
    enabled: bool = True,
    dictionary_enabled: bool = True,
    ai_polish_enabled: bool = False,
    ai_api_base_url: str = "",
    ai_api_key: str = "",
    ai_model: str = "",
) -> str:
    options = TextPipelineOptions(
        mode=mode,
        enabled=enabled,
        dictionary_enabled=dictionary_enabled,
        ai_polish_enabled=ai_polish_enabled,
        ai_api_base_url=ai_api_base_url,
        ai_api_key=ai_api_key,
        ai_model=ai_model,
    )
    return TextProcessingPipeline().process(text, options)


def polish_text_with_api(
    text: str,
    mode: str,
    api_base_url: str,
    api_key: str,
    model: str,
    timeout_seconds: int = 30,
) -> str:
    if not api_base_url:
        raise RuntimeError("未配置 AI 润色 API 地址")
    if not api_key:
        raise RuntimeError("未配置 AI 润色 API Key")

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("缺少 requests，请先安装依赖：pip install -r requirements.txt") from exc

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": _polish_system_prompt(mode),
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
        polished = _extract_chat_text(response.json())
    except Exception as exc:
        raise RuntimeError(redact_secret(str(exc))) from exc

    if not polished:
        raise RuntimeError("AI 润色 API 响应中没有可用文本")
    return tidy_text(polished.strip().strip('"“”'))


def _polish_system_prompt(mode: str) -> str:
    if mode == "code":
        return "你是开发者语音输入润色助手。请将用户文本整理为适合写代码或技术沟通的表达，只输出结果。"
    if mode == "document":
        return "你是文档写作润色助手。请将用户文本整理为正式、清晰的书面表达，只输出结果。"
    return "你是聊天输入润色助手。请去除口语废话，保留自然语气，只输出润色后的文本。"


def _extract_chat_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]

    for key in ("text", "data", "result", "output"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            nested = _extract_chat_text(value)
            if nested:
                return nested
    return ""
