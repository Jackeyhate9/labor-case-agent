# 两种版本的边界

## 5090 本地路演版

入口：仓库根目录 `start-roadshow-5090.bat`。

这个版本只供当前演示电脑使用，不作为公开安装包分发。启动脚本通过环境变量
接入以下现有资源，不复制也不重新下载模型：

| 能力 | 路演配置 |
|---|---|
| 语言模型 | 本机 Ollama：`http://127.0.0.1:11434/v1` |
| OCR | Ollama `unlimitedocrlocal:latest`，失败时保留 RapidOCR 兜底 |
| 录音转写 | `.venv-moss` + `dist/models/MOSS-Transcribe-Diarize` |
| 语义检索 | `.venv-moss` + `dist/models/bge-m3` |
| 可选向量模型 | `dist/models/Nemotron-3-Embed-1B-BF16` |

案件数据和设置写入 `%LOCALAPPDATA%\LaborCaseAgent-Roadshow`，不会覆盖个人安装版的
`%LOCALAPPDATA%\LaborCaseAgent`。

启动前脚本会检查 Ollama、BGE-M3 权重和 MOSS Python 环境。任一关键资源缺失时会
明确报错，不会静默退化后继续路演。

## 个人安装版

分发文件：`dist/LaborCaseAgent-UserSetup.exe`。

安装器只包含桌面工作台、API 和 RapidOCR CPU 基础能力，不包含 Ollama 模型、
BGE-M3、MOSS、Nemotron 或 CUDA/PyTorch 运行时。首次打开时：

1. 基础建案、材料整理、RapidOCR、金额计算、文书和导出可以直接使用。
2. 用户可以选择本机 Ollama，填写 `http://127.0.0.1:11434/v1` 和模型名称。
3. 用户可以选择外部 OpenAI 兼容 API；API Key 使用 Windows 当前用户 DPAPI 加密。
4. 可选模型会显示体积、硬件要求、许可证和来源。
5. 只有用户同时确认许可证和下载行为后，程序才开始下载模型与隔离运行环境。
6. 用户也可以登记已经存在的模型根目录；登记只保存路径，不复制模型。

个人安装版默认不自动联网、不自动下载大模型，也不会携带开发者电脑上的 API Key、
Ollama 模型或案件数据。

## 构建

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-editions.ps1
```

构建输出：

- `dist/LaborCaseAgent-UserSetup.exe`：用于向用户分发的明确命名副本。
- `dist/edition-build-manifest.json`：记录安装器哈希、体积及两个版本的资源边界。
- `start-roadshow-5090.bat`：当前电脑的路演入口。

两个入口复用同一个桌面程序二进制，但运行时 edition、数据目录和 Provider
来源不同。这样既避免重复维护两个应用，也防止路演机配置进入用户安装包。
