# 语音输入器

一个面向 Windows 桌面的语音输入法原型。用户可以通过悬浮窗或全局快捷键录音，使用本地离线模型、HTTP 云端 API 或 WebSocket 实时识别中文语音，并将结果复制或插入到当前输入位置。

## 功能特性

- 桌面悬浮窗，支持托盘驻留。
- 麦克风录音并保存为临时 WAV 音频。
- 使用 `faster-whisper` 进行本地离线中文语音识别。
- 识别结果可编辑、整理、复制和插入。
- 支持三种识别模式：本地兜底、HTTP API 一次性识别、WebSocket 实时识别。
- 支持全局快捷键开始/停止录音。
- 保存最近语音输入历史。
- 设置模型大小、模型路径、语言、快捷键和自动插入。

## 技术栈

- Python 3.12
- PySide6：桌面 GUI
- sounddevice + numpy：麦克风录音与音频处理
- faster-whisper：本地离线语音识别
- OpenCC：繁体中文转简体中文后处理
- requests：云端 ASR API 调用
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
- `local_beam_size`：本地模型搜索宽度，数值越小响应越快，默认 `1`。
- `history_limit`：历史记录数量。

## 历史记录存储

当前采用轻量 JSON 本地历史存储，数据默认写入 `data/history.json`。代码中通过 `HistoryRepository` 抽象隔离历史记录读写，当前实现为 `JsonHistoryRepository`，后续如需升级 SQLite，只需要新增仓储实现并替换注入点，不需要重写 UI 逻辑。

## 常用命令

```powershell
python -m app
python -m unittest discover -s tests
python -m ruff check app tests
```

## 项目结构

```text
app/
  asr/       离线语音识别封装
  audio/     麦克风录音
  controllers/ 后台识别、实时识别和翻译 Worker
  input/     全局快捷键、复制和粘贴输入
  config.py  设置读写
  history.py 历史记录仓储抽象与 JSON 实现
  main_window.py 桌面悬浮窗
  session_state.py 会话诊断状态
config/
docs/
tests/
```

## 原创功能说明

本项目原创实现包括桌面悬浮交互、录音状态管理、识别流程封装、历史记录、配置页、文本整理和复制/插入流程。语音识别模型、GUI 框架、录音库和输入模拟库为第三方依赖，已在技术栈中列明。

## Demo 视频

待补充：提交前将 Demo 视频链接填写在此处。

## 开发说明

比赛要求保持持续交付。建议每个功能点单独提交 commit，PR 描述写清楚变更内容，不要在截止前一次性导入全部代码。

## 安全说明

- 不要将 `config/settings.json`、API Key 或包含密钥的截图上传到公开仓库。
- API Key 和 WebSocket API Key 输入框会以密码形式显示，接口错误信息会对常见密钥格式做脱敏处理。

## WebSocket 实时识别协议

WebSocket 模式会在连接建立后发送一条 JSON 启动消息，然后持续发送 `pcm_s16le` 二进制音频块，停止时发送 `{"type": "end"}`。服务端返回 JSON 时，程序会优先读取 `text`、`transcript`、`transcription` 或 `partial` 字段，并根据 `is_final`、`final`、`completed` 或 `type=final` 判断是否为最终文本。

如果 WebSocket 地址包含 `dashscope` 或阿里云 `api-ws`，程序会自动使用百炼 Paraformer 实时识别协议：发送 `run-task`，等待 `task-started` 后上传音频，停止时发送 `finish-task`，并解析 `result-generated` 事件。

## 测试说明

当前测试覆盖配置读写、历史记录数量限制和文本整理逻辑：

```powershell
python -m unittest discover -s tests
```

麦克风录音、离线识别和外部应用插入需要在 Windows 桌面环境中手动验证。

## 许可证

比赛作品阶段暂未指定许可证，可在正式开源前补充。
