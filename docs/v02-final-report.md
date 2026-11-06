# Labor Case Agent v0.2 最终报告

验收日期：2026-07-22。v0.1 基线提交 `afce2d2` 保留，v0.2 升级计划提交为 `70a33de`。

## 1. 完成模块

- OCR：`EvidenceRegion` 显式坐标、Unlimited‑OCR 原生检测标记解析、GPU 检测、Paddle/Windows/RapidOCR 降级、图片/PDF 定位与区域裁剪。
- 原件预览：PNG/JPG/JPEG、PDF.js、DOCX 安全 HTML、CSV/XLSX 有界表格、文本及 Range 音频流；派生文件与原件分离保存。
- 音频：FFmpeg 16 kHz 单声道派生、MOSS Transcribe Diarize、说话人/时间戳片段、片段点击播放及事实来源回链。
- 检索：BGE‑M3 与 Nemotron‑3‑Embed‑1B provider、`embedding_model_version`、确认事实索引、语义搜索及旧案件词法降级。
- 推理辅助：Evidence → Fact → TimelineEvent → Claim 图谱查询、仅确认事实的证据审查、六类用人单位抗辩场景。
- 设置/安全：离线与联网 provider 状态、原子持久化、本地能力包自主安装、OpenAI-compatible API 配置和连接测试、Windows DPAPI 密钥加密、案件目录隔离、危险文件/伪装检查、身份证/手机号脱敏、结构化日志过滤。
- 桌面：Tauri v2、FastAPI PyInstaller sidecar、Next standalone + Node、SQLite/Alembic 自动升级、离线 WebView2 NSIS 安装器。

## 2. 验收结果

| 层级 | 结果 |
| --- | --- |
| Backend | 111/111；既有 pytest-cov 总覆盖率基线 93% |
| Frontend | 25/25 |
| Playwright integration | 4/4：v0.1 核心闭环，以及 v0.2 真实图片 OCR/区域/事实、真实录音转写/播放/事实、真实 ZIP 导出 |
| Next.js | `npm run build` 通过，类型检查与生产构建通过 |
| 数据库 | `0001_initial` → `0005_audio_fact_provenance (head)`；保留 v0.1 数据与导出根文件 |
| Desktop | sidecar health、RapidOCR、cargo check、NSIS、静默安装与已安装启动验证见 Windows 发布说明 |

后端相对 v0.1 新增 78 项测试，超过要求的 20 项；覆盖 OCR Region、Audio、Embedding、Preview、Export、Settings、安全、Provider 与迁移。模型 worker 是独立子进程入口，真实推理由集成测试覆盖；API/provider/业务代码计入 93% 报告。

## 3. 主要新增文件

- 后端：`alembic/versions/0002..0005`；`audio.py`、`embedding.py`、`evidence_graph.py`、`preview.py`、`review_agents.py`、`security.py`、`settings.py`；`providers/` 与 `model_workers/`。
- 前端：`evidence-preview.tsx`、`settings-panel.tsx`、三个 v0.2 测试文件和 `e2e-integration/v02-multimodal.spec.ts`。
- 桌面/构建：`apps/desktop/`；`build-sidecar.ps1`、`prepare-desktop-web.ps1`、`build-desktop.ps1`、`desktop_api_launcher.py`。
- 样例/文档：`wage-call.wav`、`v02-evidence-locator.png`、`unlimited-ocr.md`、`security-v02.md`、`model-manifest-v02.md`、`windows-release.md` 与本报告。

## 4. 模型与性能

| 模型 | 实测结果 |
| --- | --- |
| Unlimited‑OCR | RTX 5090 Laptop；40.3 秒；684 字符；11 个持久区域；约 12.25 GiB 观察峰值显存 |
| RapidOCR CPU fallback | 两张真实虚构截图分别 4.71 秒、3.65 秒 |
| MOSS Transcribe Diarize | 7.247 秒中文虚构录音；Playwright 完整流程 26.1 秒；产生时间戳片段与来源事实 |
| BGE‑M3 | 本地 GPU 实测；1024 维；`bge-m3-v1` 索引和语义检索通过 |
| Nemotron‑3‑Embed‑1B | 本地 GPU 实测；2048 维且 L2 norm=1；`nemotron-v1` 索引和语义检索通过 |

构建机为 NVIDIA GeForce RTX 5090 Laptop（24,463 MiB）。Unlimited 的 CUDA 路径不支持纯 CPU；无 GPU 时自动继续到 CPU provider。四套权重已放在 `dist/models`（147 个模型文件、约 14.43 GiB），`checksums.sha256` 提供逐文件校验；安装器不会隐式联网下载。

## 5. 交付物与截图

- 规范安装器：`dist/LaborCaseAgent.exe`（Windows x64 NSIS；2026-07-27 重建，507,551,954 字节；SHA-256 `838774dfdb40457506cd2567883418a75908da6798daca1307ddace11aabc321`；未签名）。
- 模型载荷：`dist/models/`。
- 运行截图：[`images/v02-evidence-locator.png`](images/v02-evidence-locator.png)，展示原图、OCR 框和右侧文本定位轨。

## 6. 已知限制

安装器未签名且没有自动更新；回环 API 没有随机会话令牌；大型 CUDA/MOSS/embedding 运行时不嵌入 NSIS，需要用户在能力设置中另行下载；Windows OCR adapter 未完成实际识别；LLM 设置不代表证据审查会调用云模型；模型输出与法律结论均须人工复核。完整清单见 [`known-limitations.md`](known-limitations.md) 和 [`security-v02.md`](security-v02.md)。
