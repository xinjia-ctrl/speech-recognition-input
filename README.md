# XinVoice

XinVoice 是一个面向 Windows 桌面的语音输入法原型。用户可以通过悬浮窗或全局快捷键录音，使用本地离线模型、HTTP 云端 API 或 WebSocket 实时识别中文/英文语音，并将结果复制或插入到当前输入位置。

## 功能特性

- 桌面悬浮窗，支持托盘驻留。
- 麦克风录音并保存为临时 WAV 音频。
- 使用 `faster-whisper` 进行本地离线中文/英文语音识别。
- 识别结果可编辑、整理、复制和插入。
- 支持三种识别模式：本地离线、HTTP API 一次性识别、WebSocket 实时识别。
- HTTP API 失败时可自动降级到本地 faster-whisper，保障云端不可用时仍能输入。
- 支持全局快捷键开始/停止录音。
- 支持配置检查、识别诊断、规则后处理、词典校正、AI 润色和中英双向翻译。
- 保存最近语音输入历史。
- 设置模型大小、模型路径、语言、快捷键、自动插入和历史记录数量。

## 技术栈

- Python 3.12
- PySide6：桌面 GUI
- sounddevice + numpy：麦克风录音与音频处理
- faster-whisper：本地离线语音识别
- OpenCC：繁体中文转简体中文后处理，未安装时使用内置基础映射兜底
- requests：HTTP ASR、翻译和 AI 润色 API 调用
- websocket-client：WebSocket 实时语音识别
- pynput：全局快捷键
- pyperclip + pyautogui：剪贴板与粘贴输入

## 环境要求

- Windows 10/11
- Python 3.12
- 可用麦克风
- 首次运行 `faster-whisper` 模型时需要准备模型文件；如果使用模型名，依赖库可能会下载模型缓存。

## 安装与启动

基础桌面功能安装：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app
```

按识别模式追加安装：

```powershell
pip install -r requirements-local.txt      # 本地 faster-whisper 识别
pip install -r requirements-cloud.txt      # HTTP API、翻译、AI 润色
pip install -r requirements-websocket.txt  # WebSocket 实时识别
```

比赛评审或完整 Demo 环境可一次性安装全部运行依赖：

```powershell
pip install -r requirements-local.txt -r requirements-cloud.txt -r requirements-websocket.txt
```

开发检查工具单独安装：

```powershell
pip install -r requirements-dev.txt
```

Windows 打包工具单独安装：

```powershell
pip install -r requirements-build.txt
.\scripts\build_windows.ps1
```

如果系统 PowerShell 禁止激活脚本，可以改用：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-local.txt -r requirements-cloud.txt -r requirements-websocket.txt
.\.venv\Scripts\python.exe -m app
```

## 配置说明

默认配置示例位于 `config/settings.example.json`。应用保存设置后会生成 `config/settings.json`。

主要配置项：

- `model_size`：本地 Whisper 快捷模型，默认 `base`，界面默认提供 `tiny`、`base`、`small`。
- `model_path`：本地模型目录，留空时使用 `model_size`；`medium`、`large` 等更大模型建议先下载到本地后填写路径，或改用云端 API 模式。
- `asr_provider`：识别模式，`local` 表示本地离线识别，`api` 表示 HTTP 云端 API 识别，`websocket` 表示 WebSocket 实时识别。
- `fallback_to_local`：HTTP API 识别失败后是否自动使用本地模型兜底，默认开启。
- `api_base_url`：云端 ASR 接口地址，API 模式必填。
- `api_key`：云端 ASR 密钥，真实配置文件 `config/settings.json` 已被 `.gitignore` 忽略。
- `api_model`：云端 ASR 模型名，可按服务商要求填写。
- `translation_api_base_url`：翻译接口地址，使用“中翻英/英翻中”功能时必填。
- `translation_api_key`：翻译接口密钥，真实配置文件 `config/settings.json` 已被 `.gitignore` 忽略。
- `translation_model`：翻译模型名。
- `websocket_url`：WebSocket 实时识别地址，WebSocket 模式必填。
- `websocket_api_key`：WebSocket 实时识别密钥，适合百炼等与 HTTP API 使用不同密钥的服务；留空时会尝试复用 `api_key`。
- `websocket_model`：WebSocket 实时识别模型名。
- `realtime_chunk_ms`：实时音频发送块大小，默认 `200` 毫秒。
- `websocket_final_wait_ms`：停止实时识别后等待最终结果的时间，默认 `1500` 毫秒。
- `language`：识别语言，默认 `zh`。
- `hotkey`：全局快捷键，默认 `ctrl+alt+space`。
- `auto_insert`：识别完成后是否自动插入到当前输入位置。
- `preview_before_insert`：自动插入前是否保留预览确认。
- `postprocess_enabled`：是否启用规则后处理。
- `postprocess_mode`：文本场景模式，支持 `chat`、`document`、`code`。
- `dictionary_correction_enabled`：是否启用本地词典校正。
- `ai_polish_enabled`：是否启用云端 AI 润色。
- `ai_polish_api_base_url`：AI 润色接口地址。
- `ai_polish_api_key`：AI 润色接口密钥。
- `ai_polish_model`：AI 润色模型名。
- `local_beam_size`：本地模型搜索宽度，数值越小响应越快，默认 `1`。
- `history_limit`：历史记录数量。
- `sample_rate`：录音采样率，默认 `16000`。

HTTP ASR 通用接口使用 OpenAI 风格的 `/v1/audio/transcriptions` 文件上传协议。百炼 Qwen-ASR 使用 `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`，推荐模型为 `qwen3-asr-flash`；如果配置了 `websocket_api_key`，百炼 HTTP ASR 会优先复用该 Key，避免拿其他服务商的 `api_key` 调用百炼接口。

## 历史记录存储

当前采用轻量 JSON 本地历史存储，数据默认写入 `data/history.json`。代码中通过 `HistoryRepository` 抽象隔离历史记录读写，当前实现为 `JsonHistoryRepository`，后续如需升级 SQLite，只需要新增仓储实现并替换注入点，不需要重写 UI 逻辑。

更完整的运行诊断、配置字段和历史数据结构说明见 [docs/runtime_data.md](docs/runtime_data.md)。

## 常用命令

```powershell
python -m app
python -m unittest discover -s tests
python -m ruff check app tests
.\scripts\build_windows.ps1
```

## 项目结构

```text
app/
  asr/       本地、HTTP API、WebSocket 识别 Provider
  audio/     麦克风录音
  controllers/ 后台识别、实时识别和翻译 Worker
  input/     全局快捷键、复制和粘贴输入
  ui/        悬浮球、输入框、设置页、诊断页和样式
  config.py  设置读写
  history.py 历史记录仓储抽象与 JSON 实现
  main_window.py XinVoice 主窗口
  session_state.py 会话诊断状态
config/
docs/
tests/
```

更完整的模块边界和运行流程见 [docs/architecture.md](docs/architecture.md)。

## 原创功能说明

本项目原创实现包括桌面悬浮交互、录音状态管理、本地/HTTP/WebSocket ASR Provider 封装、百炼 Qwen-ASR 和 Paraformer 实时协议适配、历史记录、配置检查、诊断信息、文本整理、翻译、复制和插入流程。语音识别模型、GUI 框架、录音库、网络库和输入模拟库为第三方依赖，已在技术栈中列明。

## Demo 视频

[B 站 Demo 视频](https://www.bilibili.com/video/BV1d2Go6HEnu/?pop_share=1&spm_id_from=333.40164.0.0&vd_source=7a2907c97849e6c6c07ed23647d8d8bc)

## 开发说明

比赛要求保持持续交付。建议每个功能点单独提交 commit，PR 描述写清楚变更内容，不要在截止前一次性导入全部代码。

版本号统一维护在 `app/version.py`。Windows 打包和发布流程见 [docs/release.md](docs/release.md)。

## 安全说明

- 不要将 `config/settings.json`、API Key 或包含密钥的截图上传到公开仓库。
- API Key 和 WebSocket API Key 输入框会以密码形式显示，接口错误信息会对常见密钥格式做脱敏处理。

## WebSocket 实时识别协议

WebSocket 模式会在连接建立后发送一条 JSON 启动消息，然后持续发送 `pcm_s16le` 二进制音频块，停止时发送 `{"type": "end"}`。服务端返回 JSON 时，程序会优先读取 `text`、`transcript`、`transcription` 或 `partial` 字段，并根据 `is_final`、`final`、`completed` 或 `type=final` 判断是否为最终文本。

如果 WebSocket 地址包含 `dashscope` 或阿里云 `api-ws`，程序会自动使用百炼 Paraformer 实时识别协议：发送 `run-task`，等待 `task-started` 后上传音频，停止时发送 `finish-task`，并解析 `result-generated` 事件。

## 测试说明

当前测试覆盖配置读写、配置检查、ASR Provider 选择、HTTP 失败兜底、无语音处理、提示词回显过滤、WebSocket 消息解析、文本处理、翻译结果抽取、历史记录、错误脱敏和输入控制器错误处理：

```powershell
python -m unittest discover -s tests
```

麦克风录音、真实本地模型、真实云端 API、WebSocket 实时识别和外部应用插入需要在 Windows 桌面环境中手动验证。

## 致谢

本项目基于以下开源组件构建：

- [PySide6](https://github.com/qtproject/pyside-pyside6) — Qt for Python 桌面 GUI 框架
- [sounddevice](https://github.com/spatialaudio/python-sounddevice) — 基于 PortAudio 的麦克风录音
- [NumPy](https://github.com/numpy/numpy) — 音频数据处理
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — 本地离线语音识别（基于 [OpenAI Whisper](https://github.com/openai/whisper)）
- [OpenCC](https://github.com/BYVoid/OpenCC) — 繁简中文转换
- [requests](https://github.com/psf/requests) — HTTP API 客户端
- [websocket-client](https://github.com/websocket-client/websocket-client) — WebSocket 实时通信
- [pynput](https://github.com/moses-palmer/pynput) — 全局快捷键监听
- [pyperclip](https://github.com/asweigart/pyperclip) — 跨平台剪贴板操作
- [PyAutoGUI](https://github.com/asweigart/pyautogui) — 模拟键盘输入
- [PyInstaller](https://github.com/pyinstaller/pyinstaller) — Windows 可执行文件打包
- [Ruff](https://github.com/astral-sh/ruff) — Python 代码检查与格式化

感谢以上项目的作者和维护者的出色工作。

## 许可证

本项目采用 MIT 许可证。详情见 [LICENSE](LICENSE) 文件。
