# 运行日志与数据结构说明

本文档说明应用运行时会产生哪些可观察信息，以及配置文件、历史记录文件的结构。它主要用于比赛评审、后续调试和未来扩展。

## 运行日志与诊断

当前版本以界面内诊断信息为主，暂不默认写入落盘日志文件，避免把 API Key、识别文本或用户输入内容误保存到仓库或共享环境中。

可观察的运行信息：

- 主窗口状态栏：显示待机、录音中、实时识别中、识别完成、错误等状态。
- 设置页的“诊断”页签：显示最近一次识别的首字延迟、收尾延迟、总耗时和最近错误。
- 设置页的配置检查：检查 HTTP API、WebSocket、翻译、AI 润色等配置是否缺少地址、模型或密钥。
- 命令行输出：开发运行时，Python 进程的异常栈会显示在终端，适合定位未捕获错误。

诊断字段含义：

| 字段 | 含义 | 典型用途 |
| --- | --- | --- |
| 首字延迟 | 从开始录音到第一次拿到识别文本的时间 | 判断 WebSocket 实时识别是否真正“边说边出字” |
| 收尾延迟 | 点击停止后到最终结果返回的时间 | 判断停止录音后等待是否过长 |
| 总耗时 | 本次识别从开始到结束的总时间 | 比较本地、HTTP API、WebSocket 三种模式的体验 |
| 最近错误 | 最近一次失败的脱敏错误信息 | 排查配置缺失、网络失败、模型不可用等问题 |

后续如需要引入文件日志，建议默认写入 `data/logs/app.log`，并继续让 `data/` 保持在 `.gitignore` 中。日志内容应避免记录完整 API Key、完整 Authorization 头和敏感输入文本。

## 配置文件结构

配置示例文件位于 `config/settings.example.json`，真实运行配置保存到 `config/settings.json`。真实配置文件已被 `.gitignore` 忽略，不应提交到公开仓库。

配置文件使用 UTF-8 JSON，顶层是一个对象：

```json
{
  "asr_provider": "local",
  "model_size": "base",
  "language": "zh",
  "hotkey": "ctrl+alt+space",
  "auto_insert": false,
  "preview_before_insert": true
}
```

### 基础配置

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `asr_provider` | string | `local` | 识别模式，支持 `local`、`api`、`websocket` |
| `fallback_to_local` | boolean | `true` | HTTP API 失败后是否自动切换到本地 faster-whisper 兜底 |
| `language` | string | `zh` | 识别语言，目前界面主要面向 `zh` 和 `en` |
| `hotkey` | string | `ctrl+alt+space` | 全局快捷键 |
| `auto_insert` | boolean | `false` | 识别完成后是否自动插入到当前窗口 |
| `preview_before_insert` | boolean | `true` | 自动插入前是否先显示预览 |
| `history_limit` | number | `20` | 本地历史记录最大条数 |
| `sample_rate` | number | `16000` | 录音采样率，WebSocket 和本地识别共用 |

### 本地识别配置

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `model_size` | string | `base` | 本地 faster-whisper 快捷模型名 |
| `model_path` | string | 空字符串 | 本地模型目录；填写后优先使用本地路径 |
| `local_beam_size` | number | `1` | 本地搜索宽度，越大可能更准但更慢 |

### HTTP API 识别配置

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `api_base_url` | string | 空字符串 | HTTP ASR 接口地址 |
| `api_key` | string | 空字符串 | HTTP ASR API Key |
| `api_model` | string | 空字符串 | HTTP ASR 模型名 |

HTTP API 模式适合一次性录完后上传音频识别，不负责边说边出字。

如果 `fallback_to_local` 开启，HTTP API 配置错误、网络失败、接口异常或响应中没有可用文本时，应用会使用同一段 WAV 音频自动切换到本地 faster-whisper。WebSocket 实时模式暂不自动降级，因为实时音频当前是边采集边发送，没有额外保存完整音频文件。

### WebSocket 实时识别配置

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `websocket_url` | string | 空字符串 | WebSocket 实时识别地址 |
| `websocket_api_key` | string | 空字符串 | WebSocket 专用 API Key，留空时可复用 `api_key` |
| `websocket_model` | string | 空字符串 | WebSocket 实时识别模型名 |
| `realtime_chunk_ms` | number | `200` | 每次发送的音频块时长 |
| `websocket_final_wait_ms` | number | `1500` | 停止录音后等待最终结果的时间 |

WebSocket 模式适合实时预览。不同厂商的协议差异较大，当前代码已对通用 JSON 协议和百炼 Paraformer 实时协议做了适配。

### 文本处理与翻译配置

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `postprocess_enabled` | boolean | `true` | 是否启用规则后处理 |
| `postprocess_mode` | string | `chat` | 文本场景，支持 `chat`、`document`、`code` |
| `dictionary_correction_enabled` | boolean | `true` | 是否启用本地词典校正 |
| `ai_polish_enabled` | boolean | `false` | 是否启用云端 AI 润色 |
| `ai_polish_api_base_url` | string | 空字符串 | AI 润色接口地址 |
| `ai_polish_api_key` | string | 空字符串 | AI 润色 API Key |
| `ai_polish_model` | string | 空字符串 | AI 润色模型名 |
| `translation_api_base_url` | string | 空字符串 | 翻译接口地址 |
| `translation_api_key` | string | 空字符串 | 翻译 API Key |
| `translation_model` | string | 空字符串 | 翻译模型名 |

处理顺序为：本地词典校正、规则清洗、可选 AI 润色。翻译功能由用户在预览框手动触发，不会默认替换识别结果。

## 历史数据结构

历史记录默认保存到 `data/history.json`。`data/` 已被 `.gitignore` 忽略，因此本地历史不会进入公开仓库。

文件结构是一个 JSON 数组，最新记录排在最前：

```json
[
  {
    "text": "今天下午三点开会。",
    "created_at": "2026-05-25T11:30:00"
  }
]
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `text` | string | 识别、整理或编辑后的最终文本 |
| `created_at` | string | 本地时间 ISO 格式，精确到秒 |

历史记录写入规则：

- 空文本不会写入历史。
- 新记录插入数组开头。
- 超过 `history_limit` 后会截断旧记录。
- 清空历史时会写入空数组 `[]`。

当前实现通过 `HistoryRepository` 协议隔离读写接口，默认实现是 `JsonHistoryRepository`。后续如果历史记录需要搜索、分页、标签或跨设备同步，可以新增 SQLite 或云端仓储实现，而不需要重写 UI 调用层。
