# 当前仓库与环境审计

审计日期：2026-07-22（Asia/Shanghai）

## 仓库状态

- 工作区初始状态仅包含空 Git 仓库，无已有源码或用户材料。
- 初始分支 `master` 尚无提交；开发分支为 `codex/labor-case-agent`。
- 因无既有文件，本次初始化不存在覆盖用户改动的风险。

## 运行环境

| 项目 | 实测结果 | 决策 |
| --- | --- | --- |
| 操作系统 | Windows / PowerShell | 提供 Windows 优先命令，同时保持容器兼容 |
| Python | 3.11.9 | 后端基线 Python 3.11 |
| Node.js / npm | 24.14.0 / 11.9.0 | 前端开发可用，CI 使用 Node 22 LTS |
| Git | 2.55.0.windows.2 | 可用 |
| Docker | CLI 29.6.1；daemon 未运行 | Docker Compose 为可选路径，SQLite 本机路径不依赖 Docker |
| PostgreSQL | `psql` 不在 PATH | 默认 SQLite；Compose 提供 PostgreSQL 16 |
| Ollama | 11434 端口监听；有本地文本、视觉和 embedding 模型 | 默认关闭 LLM，用户显式启用 Ollama 后才发送材料 |
| GPU | NVIDIA RTX 5090 Laptop GPU，24GB | 足以运行本地 OCR/模型，但不是核心功能前提 |
| OCR | 系统无 Tesseract；初始 Python 无 RapidOCR/PaddleOCR | 安装 RapidOCR provider；不可用时显式降级为人工录入，不伪造结果 |
| PDF/DOCX | PyMuPDF、python-docx 已存在 | 仍由项目虚拟环境固定依赖版本 |
| 磁盘 | E 盘约 174 GiB 可用 | 本地证据目录按案件隔离 |
| 端口 | 11434 被 Ollama 使用；3000/8000/5432 空闲 | Web 3000、API 8000、PostgreSQL 5432 |

## 约束与风险

1. Docker daemon 未运行，因此验收不能依赖容器服务。
2. OCR 模型首次安装/初始化可能需要较大下载和较长启动时间；系统必须保留 OCR 失败原文与人工输入路径。
3. 开发模式没有账户体系，案件隔离通过单机 owner scope 和资源归属校验实现；多用户生产部署前必须接入强认证。
4. 真实劳动材料高度敏感。测试仅使用明确标注为虚构的数据，不进入遥测、公共错误追踪或外部模型。

## 结论

环境不存在阻止 MVP 核心闭环的硬性问题。采用“SQLite + 本地文件 + 可选 RapidOCR + 默认禁用 LLM”的离线优先基线；PostgreSQL、Ollama 与云模型均作为可显式启用的 provider。

