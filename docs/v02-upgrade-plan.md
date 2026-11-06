# Labor Case Agent v0.2 升级计划

日期：2026-07-22  
基线提交：`afce2d2`  
目标：Multimodal Evidence Intelligence + Desktop Distribution

## 1. v0.1 基线与当前架构

### 已验证基线

- 后端：FastAPI + SQLAlchemy + Alembic + SQLite，21/21 测试通过，语句覆盖率 93%。
- 前端：Next.js 15 + React 19 + TanStack Query，3/3 测试及生产构建通过。
- 真实流程：Playwright 驱动 Next.js、FastAPI、SQLite 与 RapidOCR，1/1 通过。
- 导出：现有 ZIP 路径、成员名称、DOCX/XLSX/JSON 和 manifest 视为 v0.1 兼容契约。

### 现有模块

```text
apps/web
  └─ Next.js 工作台 ──HTTP──> apps/api/app/main.py
                                  ├─ services.py：上传、解析、OCR、事实、导出
                                  ├─ models.py：Evidence/Page/Region/Fact/Timeline/Claim
                                  └─ SQLite/Alembic 0001_initial
```

`EvidenceRegion` 已存在，但 `bounding_box` 仍是 JSON 文本，解析流程未写入区域；`source_region_id` 已为事实回链预留。v0.2 在原表上做兼容迁移，不删除 Evidence、现有字段或导出成员。

## 2. 修改范围

### 数据层与迁移

- 新增 `0002_multimodal_evidence`：
  - `EvidenceRegion` 增加 `bbox_x/y/width/height`、`created_at`，保留 `bounding_box` 兼容读取。
  - 新增 `AudioSegment`，保存说话人、起止秒、文本、置信度和来源证据。
  - 新增版本化 `EvidenceEmbedding`，模型版本是向量空间的一部分，禁止跨版本直接比较。
  - 新增显式图边 `EvidenceLink`，支持 Evidence/Fact/Timeline/Claim 的带类型关系；已有外键通过读取适配器继续成为图边。
  - Evidence 增加派生预览状态/类型元数据，但原件路径、哈希和内容永不变更。

### 后端新增深模块

```text
app/providers/ocr.py       OCRProvider + OCRRouter
app/providers/audio.py     AudioProvider + MOSS provider/router
app/providers/embedding.py BGE-M3/Nemotron + version router
app/preview.py             图片/PDF/DOCX/CSV/XLSX 派生预览
app/evidence_graph.py      统一图查询与审查输入
app/security.py            扩展名/MIME、脱敏、日志过滤、目录隔离
```

保持 `main.py` 现有 API 不变，仅增加 v0.2 路由；保持 `services.py` 的 v0.1 公共行为，并将新能力从旁路接入。

### OCR 路由

运行优先级：

1. `UnlimitedOCRProvider`：仅本机、GPU 优先；模型/依赖/显存不足时明确报告 unavailable。
2. `PaddleOCRProvider`：GPU/CPU。
3. `WindowsOCRProvider`：Windows 可用时启用。
4. `RapidOCRProvider`：保留 v0.1 的真实离线兼容路径，并提供文本框坐标。
5. `VisionLLMOCRProvider`：必须显式开启，外发前需确认，默认禁用。

Router 返回实际 Provider、device、降级原因、页尺寸与归一化区域。Unlimited-OCR 的“CPU fallback”定义为自动切换到 CPU OCR Provider，而不是在 3B BF16 模型上静默进入不可接受的 CPU 推理。

### 预览与多模态

- 图片：原件流式只读预览，OCR 坐标覆盖层与区域裁剪 API。
- PDF：PDF.js 客户端页渲染；后端 PyMuPDF 生成独立页面预览用于 OCR/裁剪。
- DOCX：使用 `python-docx` 生成经过转义的只读 HTML 派生预览。
- CSV/XLSX：服务端输出限行、限列的结构化表格预览。
- 音频/视频：原件通过支持 Range 的受控文件接口播放；FFmpeg 生成独立标准 WAV；MOSS 输出 `AudioSegment`，点击转写片段设置媒体 `currentTime`。

所有派生物写入 `data/cases/{case_id}/derived/`，原件只读保存在 `original/`，导出继续包含原始哈希。

### Evidence Graph 与 Agent

- 查询接口按案件返回节点、边、来源和确认状态，并支持从 Claim 反查证据链。
- Evidence Review 只消费 `user_confirmed` 事实，输出优势、薄弱点、冲突与补证建议。
- Adversarial Review 扩展六类指定场景，并把每项输出标记为“可能抗辩”，不生成事实或对方证据。

### Settings 与本地部署

- 设置页显示 OCR/Audio/LLM/Embedding Provider、device、模型路径、可用性与降级原因。
- 离线模式禁止网络 Provider；联网模式只允许显式配置的 OpenAI-compatible endpoint。
- 服务只绑定 loopback；生产配置使用随机本地会话令牌、严格 CORS、请求体日志禁用和案件级目录校验。

### Windows 桌面分发

- Tauri 2 作为桌面壳；Rust 在启动期拉起 PyInstaller FastAPI sidecar 与 Next.js standalone sidecar，健康检查通过后显示本地工作台。
- 生成 Tauri 主程序 `LaborCaseAgent.exe` 与 NSIS 安装器；WebView2 采用离线 installer 配置。
- 用户数据与模型不写安装目录：数据位于 `%LOCALAPPDATA%/LaborCaseAgent/data`，模型位于 `%LOCALAPPDATA%/LaborCaseAgent/models`。
- 模型可在 `dist/models/manifest.json` 声明；体积过大的模型默认首次启动经用户确认下载并校验 SHA-256。离线发布包可额外放入同结构模型目录。

## 3. 新增依赖

### 核心小依赖

- 后端：PyMuPDF（当前环境已有，声明为正式依赖）、`bleach`（HTML 清理）、`filetype`（内容嗅探）。
- 前端：`pdfjs-dist`；不引入云端预览组件。
- 桌面：Tauri 2、shell/process 插件、PyInstaller；Rust/MSVC 已存在。

### 可选模型依赖（隔离 extras/worker）

- OCR：Transformers/PyTorch Unlimited-OCR；PaddleOCR/PaddlePaddle。
- Audio：MOSS-Transcribe-Diarize、Torch/Torchaudio、Transformers；FFmpeg 已存在。
- Embedding：Sentence Transformers，兼容 `BAAI/bge-m3` 与 `nvidia/Nemotron-3-Embed-1B-BF16`。

模型依赖不强制进入轻量核心安装，避免破坏 v0.1；Provider 通过能力探测注册。

## 4. 本机与模型审计

| 项目 | 当前证据 | 决策 |
|---|---|---|
| GPU | RTX 5090 Laptop，24,463 MiB | 可进行 BF16 GPU 验收，同时必须跑 CPU 降级 |
| Unlimited-OCR | 未在 HF 缓存或有限深度模型目录发现 | 实现 Provider；下载后真实基准，不伪报已安装 |
| MOSS Transcribe Diarize | 未发现 | 隔离安装并下载 0.9B 模型做真实音频验收 |
| BGE-M3 | 找到约 1.93GB 和 4.59GB 两份 | 先校验完整性与许可；通过配置复用，不复制到 Git |
| Nemotron 1B | 未发现 | 可选下载；保持 BGE 默认与旧向量兼容 |
| FFmpeg | 8.0.1 可用 | 用于音视频标准化与播放兼容 |
| Rust/MSVC | rustc/cargo 1.91、VS 2022 Build Tools | 可构建 Tauri |
| LibreOffice/ClamAV | 未安装 | DOCX 用安全 HTML 预览；扩展名/内容检查不冒充杀毒扫描 |

Unlimited-OCR 官方模型为 3B BF16、MIT，官方 Transformers 示例以 NVIDIA GPU 为基线；MOSS 为 0.9B、Apache-2.0，官方代码同时给出 CUDA BF16 与 CPU FP32 路径；Nemotron 采用 OpenMDW-1.1，必须在分发前保留单独许可审查记录。

## 5. 测试与验收门

采用垂直 TDD：每个能力先增加一个公共 API/用户行为测试，确认 RED，再实现至 GREEN；每个模块完成后运行 v0.1 全量回归。

- 后端至少新增 20 项：Region 坐标/裁剪、PDF 页、预览隔离、音频段、Range、安全、Provider 探测/降级、embedding 版本隔离、图查询、Agent confirmed-only、兼容导出。
- 前端至少新增 10 项：区域点击、页切换、图片/PDF/表格/音频预览、片段跳播、Provider 状态、离线设置、错误/空状态。
- Playwright 至少新增 3 条真实流程：图片 OCR 区域→确认事实；音频→真实转写→跳播→事实；完整案件兼容导出。
- 覆盖率不得低于 93%；旧 21+3+1 测试不得删除或弱化。
- 真实模型测试按 `model` 标记单独运行，并在最终报告记录未安装、GPU 与 CPU 各自的实际结果；普通 CI 验证路由降级，不用 mock 冒充模型推理。

## 6. 主要风险与控制

| 风险 | 控制 |
|---|---|
| 新模型 remote code / 供应链 | 固定 revision、记录许可证与哈希；模型 worker 隔离；默认不联网 |
| 3B OCR 或音频模型造成 OOM | 启动前显存探测、单任务队列、失败后释放 CUDA cache 并降级 |
| OCR 坐标系错位 | 保存原始像素尺寸和像素 bbox；API 同时返回 0..1 归一化坐标；旋转纳入测试 |
| PDF/DOCX 主动内容 | PDF.js 禁脚本；DOCX 只提取文本/表格并 HTML 转义；不执行宏或外部链接 |
| 音视频解析攻击 | 扩展名、MIME、magic bytes、大小/时长限制；FFmpeg 子进程无 shell、限时、独立目录 |
| 多模型向量混用 | `embedding_model_version` 强制过滤；旧案件保持词法搜索并可后台重建索引 |
| Tauri sidecar 泄露或僵尸进程 | loopback + 随机令牌；主程序退出时终止子进程；单实例与健康检查 |
| v0.1 导出破坏 | 只增加新成员；旧成员名称、格式和 manifest 字段保留；兼容测试比较成员集合与哈希语义 |
| 安装包未签名 | 本地验收明确标记 unsigned；发布说明记录 SmartScreen 与正式签名要求 |

## 7. 回滚方案

1. 每个模块独立提交；发现回归时按提交撤销，不重写 v0.1 基线。
2. 数据库迁移 `0002` 只新增表/列；应用可通过 `FEATURE_MULTIMODAL=false` 关闭 v0.2 路由并继续读取 v0.1 数据。
3. 新 bbox 列写入时同步保留旧 `bounding_box`；回滚应用仍能读取旧字段。
4. 导出默认继续生成 v0.1 成员；v0.2 多模态成员为附加项，可通过 `EXPORT_MULTIMODAL=false` 关闭。
5. Provider 失败自动回到 v0.1 RapidOCR/确定性流程；LLM、embedding 和音频模型不成为建案、事实确认或导出的硬依赖。
6. 桌面层不迁移数据格式；卸载 Tauri 不删除 `%LOCALAPPDATA%/LaborCaseAgent/data`，用户可继续用浏览器版读取同一目录。

