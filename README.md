# 离线语音输入器

一个面向 Windows 桌面的语音输入法原型。用户可以通过悬浮窗或全局快捷键录音，使用本地离线模型识别中文语音，并将结果复制或插入到当前输入位置。

## 功能特性

- 桌面悬浮窗，支持托盘驻留。
- 麦克风录音并保存为临时 WAV 音频。
- 使用 `faster-whisper` 进行本地离线中文语音识别。
- 识别结果可编辑、整理、复制和插入。
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
- pynput：全局快捷键
- pyperclip + pyautogui：剪贴板与粘贴输入

## 环境要求

- Windows 10/11
- Python 3.12
- 可用麦克风
- 首次运行 `faster-whisper` 模型时需要准备模型文件；如果使用模型名，依赖库可能会下载模型缓存。

## 安装与启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app
```

如果系统 PowerShell 禁止激活脚本，可以改用：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app
```

## 配置说明

默认配置示例位于 `config/settings.example.json`。应用保存设置后会生成 `config/settings.json`。

主要配置项：

- `model_size`：Whisper 模型大小，默认 `base`。
- `model_path`：本地模型目录，留空时使用 `model_size`。
- `asr_provider`：识别模式，`local` 表示本地离线识别，`api` 表示云端 API 识别。
- `api_base_url`：云端 ASR 接口地址，API 模式必填。
- `api_key`：云端 ASR 密钥，真实配置文件 `config/settings.json` 已被 `.gitignore` 忽略。
- `api_model`：云端 ASR 模型名，可按服务商要求填写。
- `language`：识别语言，默认 `zh`。
- `hotkey`：全局快捷键，默认 `ctrl+alt+space`。
- `auto_insert`：识别完成后是否自动插入到当前输入位置。
- `history_limit`：历史记录数量。

## 常用命令

```powershell
python -m app
python -m unittest
```

## 项目结构

```text
app/
  asr/       离线语音识别封装
  audio/     麦克风录音
  input/     全局快捷键、复制和粘贴输入
  config.py  设置读写
  history.py 历史记录
  main_window.py 桌面悬浮窗
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

## 测试说明

当前测试覆盖配置读写、历史记录数量限制和文本整理逻辑：

```powershell
python -m unittest
```

麦克风录音、离线识别和外部应用插入需要在 Windows 桌面环境中手动验证。

## 许可证

比赛作品阶段暂未指定许可证，可在正式开源前补充。
