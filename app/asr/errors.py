from __future__ import annotations


NO_SPEECH_KEYWORDS = (
    "未识别到声音",
    "没有识别到声音",
    "没有识别到可用文字",
    "没有采集到有效音频",
    "no speech",
    "empty audio",
    "audio is empty",
)


def is_no_speech_message(message: str) -> bool:
    normalized = message.strip().lower()
    return any(keyword.lower() in normalized for keyword in NO_SPEECH_KEYWORDS)
