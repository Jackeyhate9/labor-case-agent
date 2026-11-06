# 参考仓库只读审计

检索日期：2026-07-22（Asia/Shanghai）

核验方式：通过 `agent-reach` 的 GitHub 路由（GitHub CLI / GitHub API）实时读取公开仓库元数据、默认分支头提交、根目录、README、LICENSE、依赖清单、环境变量样例及与 OCR、证据、时间线、文书、Agent/Skill、Provider、隐私有关的文件。未克隆仓库、未运行第三方代码、未复制源码。

## 结论摘要

六个 URL 在检索日均可公开访问，均未归档。最值得借鉴的是流程和数据边界，而不是直接合并代码：`worker-aid-agent` 的本地优先、人工复核与脱敏护栏；`evidence-triage-OSS` 的证据分类/检索交互；`feishu-opencode-bridge` 的共享 workflow 分层、证据台账和数据流透明度；`Mock-Court` 的对抗式多角色复核；`Partlawyer-LAA` 的地区化 DOCX 模板；`labor_rights_skills` 的渐进式 Skill 与证据采集清单。

当前决定是：**六仓均只作架构、交互和流程参考；本项目尚未引用或复制任何第三方代码。** 原因不是所有仓库都禁止复用，而是其中三仓存在强 copyleft、非标准许可或许可自相矛盾，另外三仓即使采用宽松许可，也需要逐文件归属审查、保留通知并评估外部云依赖后才适合有选择地复用。

维护日期采用默认分支头提交的提交者时间，而不是可能受 Star、Issue、标签或其他引用影响的 GitHub `updatedAt`/`pushedAt`。截至检索日，默认分支头提交分别为：Partlawyer 2026-02-25、labor_rights_skills 2026-07-09、worker-aid-agent 2026-07-04、evidence-triage 2026-01-29、Mock-Court 2026-06-18、feishu bridge 2026-05-12。

## 能力对照

| 仓库 | OCR / 文件解析 | 时间线 / 证据 | 文书 | Agent / Provider | 完全本地部署判断 |
|---|---|---|---|---|---|
| Partlawyer-LAA | 未发现案件证据 OCR；含语音技术栈 | 未发现可追溯事实/时间线模型；有地区证据清单模板 | Python + DOCX 模板，浙江/广东及工伤路径 | 单一聊天式系统提示；LiteLLM 指向本地 Ollama | 可本地运行，但体量大、依赖 CUDA/模型/TTS；不是轻量离线证据工作台 |
| labor_rights_skills | 图片/PDF 依赖宿主多模态模型；音频由本地 FunASR 处理 | evidence card + 可信度等级；没有持久化案件数据库或正式时间线实体 | Markdown 法律意见书与三类骨架模板 | 单 Skill 六阶段流程；WebSearch 补充最新法源 | 音频可本地；完整流程是否离线取决于宿主模型，实时法源检索仍需联网 |
| worker-aid-agent | 未发现原件 OCR 管线 | 本地 JSON/模板/证据清单；严格 ISO 日期时间线，带来源字符串和人工复核警告 | Markdown/HTML/`.doc` 草稿导出 | 三角色 Agent + 九个 Skills；外部模型可选且调用前确认 | 核心 App/CLI 可不接模型本地运行；浏览器草稿/导出仍需安全治理 |
| evidence-triage-OSS | Case.dev Vault 自动 OCR/提取；PDF.js | EvidenceItem 分类、标签、相关度、摘要、日期和 Vault 引用；有 timeline 视图 | 无劳动仲裁文书生成 | Case.dev LLM 分类/摘要；仓库内 skills 偏开发脚手架 | 否；OCR 需要 Case.dev API 与 Vercel Blob，持久化依赖云 Vault/Neon |
| Mock-Court | Rust 调本机 Tesseract | 会话归档/审计/成本记录；UI 有 session timeline；非案件证据台账 | 不以正式文书为主 | 多角色并行辩论；LM Studio、OpenAI、DeepSeek、Claude/中继 | 大部分可经 Docker + LM Studio + Tesseract 本地化；SearXNG/可选云 Provider 仍有外发面 |
| feishu-opencode-bridge | PDF/DOCX/XLSX 等统一解析；默认本地 Tesseract，外部 OCR 显式开启 | 已落地 evidence-extract、evidence-ledger、timeline-build、workbench-generate | docxtemplater/Python 文档管线、工作台/飞书文档/白板 | OpenCode Skills + Runtime Modules + 扩展；模型由 OpenCode Provider 决定 | 否；Bridge 可本地，但飞书消息/Base 是云端，且模型 Provider 可能外发 |

## 逐仓审计

### 1. DerpZhenjun/Partlawyer-LAA

来源：[仓库](https://github.com/DerpZhenjun/Partlawyer-LAA)、[README](https://github.com/DerpZhenjun/Partlawyer-LAA/blob/main/README.md)、[LICENSE](https://github.com/DerpZhenjun/Partlawyer-LAA/blob/main/LICENSE)、[后端入口](https://github.com/DerpZhenjun/Partlawyer-LAA/blob/main/backend/app.py)、[依赖清单](https://github.com/DerpZhenjun/Partlawyer-LAA/blob/main/requirements.txt)、[默认分支头提交](https://github.com/DerpZhenjun/Partlawyer-LAA/commit/e3d58c2c704c87b04cfd74d891972697f6f9fa8f)。

**核验事实**

- 实际用途：劳动仲裁咨询与文书生成演示平台，组合 3D 数字人 ChatVRM、GPT-SoVITS 语音克隆、本地 Ollama 和模型微调；并非证据全生命周期工作台。
- 技术栈：Python 3.10、FastAPI、Pydantic、LiteLLM、python-docx、Vue 3 + Vite + Bootstrap；另带 Next.js 13/React 的 ChatVRM 和体量很大的 PyTorch/CUDA、FunASR、GPT-SoVITS 依赖树。
- 文书：`backend/WenShu` 与 `backend/templates_docx` 按浙江、广东和工伤场景生成仲裁申请书、证据清单等 DOCX。
- OCR/时间线/证据：默认分支路径和 README 未显示案件 OCR、页/区域坐标、证据来源回链、事实确认状态或时间线实体。证据能力主要是模板输出，而非结构化证据库。
- Agent/Provider：聊天后端把固定“中国法律顾问”系统提示与用户问题发送到 LiteLLM，默认 `ollama/qwen3:1.7b`、`localhost:11434`；没有可见的多 Agent 或 Provider 注册/降级层。
- 最近维护：默认分支头为 2026-02-25 的 README 更新；检索日距该提交约 5 个月。
- 许可证：根目录 MIT；仓库同时内嵌 ChatVRM、GPT-SoVITS、大量子许可证、模型/音频/VRM 资产，根 MIT 不能自动覆盖所有第三方内容。
- 敏感信息：未在抽查的配置发现真实 API Key；`api_key="ollama"` 是本地占位。仓库包含临时音频和语音克隆资源路径、模型权重说明、编译缓存；FastAPI CORS 同时列出 `*` 与凭据，若照搬到联网部署会扩大数据暴露面。

**审计判断（推断）**

- 可借鉴：地区化文书模板目录、DOCX 字段填充流程、本地 Ollama 快速接入。
- 不适合继承：数字人/语音克隆是高资源、低核心价值分支；单提示聊天无法满足“原始材料→机器提取→用户确认→法律草稿”的分层；依赖和仓库卫生不利于可维护部署。
- 是否引用代码：否。即使 MIT 允许，若未来复用也应只挑独立模块，保留 MIT 文本/版权声明，并逐项核验嵌套项目、模型、声音与 3D 资产许可及人格权/声音权益。

### 2. jerry046918/labor_rights_skills

来源：[仓库](https://github.com/jerry046918/labor_rights_skills)、[README](https://github.com/jerry046918/labor_rights_skills/blob/master/README.md)、[LICENSE](https://github.com/jerry046918/labor_rights_skills/blob/master/LICENSE)、[证据采集说明](https://github.com/jerry046918/labor_rights_skills/blob/master/references/evidence-collection.md)、[音频依赖](https://github.com/jerry046918/labor_rights_skills/blob/master/scripts/requirements.txt)、[默认分支头提交](https://github.com/jerry046918/labor_rights_skills/commit/d6420cf709f0bb55d6ff58aae58ed09be165962d)。

**核验事实**

- 实际用途：面向中国大陆劳动纠纷的 AI Skill，以六阶段调查、证据采集、法条/案例检索和 Markdown 法律意见书为主。
- 技术栈：Markdown Skill/References；Python 音频脚本使用 FunASR、PyTorch、ModelScope、VAD/标点/说话人分离相关依赖；pytest 测试。
- OCR/解析：文本/图片/PDF 交由宿主模型直接解析，图片/PDF 需要多模态能力；音频本地 FunASR，README 称首次模型约 3GB。没有独立 OCR Router、页码/区域坐标持久化。
- 证据：统一 evidence card，包含来源与三星可信度等级，强调原始载体与补强；运行时落到 `evidence/`。可信度等级是工作提示，不等同司法证明力评分。
- 时间线：流程会组织事实，但未发现独立、可编辑、可追溯且支持模糊日期精度的 Timeline 数据模型。
- 文书：八节 Markdown 意见书模板，另有解除通知函、仲裁申请书、律师函骨架；缺失信息用占位符。
- Agent/Provider：单 Skill 渐进式披露，重资料按需读取；Provider 由宿主 AI 决定，案例补充依赖 WebSearch。
- 最近维护：默认分支头为 2026-07-09，新增法规全文；属于近期活跃，但仓库创建于 2026-06-27，历史仍短。
- 许可证：Anti-996 License v1.0，属于带使用者行为条件的非标准许可证，不是 OSI 常见宽松许可证。
- 敏感信息：音频原件宣称本地处理，但转写文本、图片/PDF 解析和 WebSearch 仍可能进入宿主模型/搜索上下文；`evidence/` 是普通目录，未显示加密、租户隔离、删除审计和密钥治理。

**审计判断（推断）**

- 可借鉴：渐进式 Skill、针对争议类型的追问、证据清单、缺失信息占位和人工核验提示。
- 不适合继承：把“法律意见书”作为自动终点、把模型能力当 OCR、用三星等级简化证明力、将原文法规/案例静态打包而缺少版本签名与更新治理。
- 是否引用代码：否。Anti-996 的附加条件会形成分发与使用合规不确定性；除非负责人和律师明确接受，限于理念/流程参考，不复制代码、提示词、模板或大段资料。

### 3. worker-aid-ai/worker-aid-agent

来源：[仓库](https://github.com/worker-aid-ai/worker-aid-agent)、[README](https://github.com/worker-aid-ai/worker-aid-agent/blob/main/README.md)、[LICENSE](https://github.com/worker-aid-ai/worker-aid-agent/blob/main/LICENSE)、[package.json](https://github.com/worker-aid-ai/worker-aid-agent/blob/main/package.json)、[时间线实现](https://github.com/worker-aid-ai/worker-aid-agent/blob/main/src/lib/timeline.mjs)、[隐私规则](https://github.com/worker-aid-ai/worker-aid-agent/blob/main/docs/PRIVACY_AND_SAFETY.md)、[默认分支头提交](https://github.com/worker-aid-ai/worker-aid-agent/commit/cd38588929f6da68e9dbc1617931e8a81030b6c9)。

**核验事实**

- 实际用途：劳动者自助、证据整理、金额粗算、法援咨询摘要和仲裁材料草稿；明确不是 AI 律师。
- 技术栈：Node.js 18+、ES Modules、pnpm，本地 HTTP App/静态 Web UI、Node 原生测试；核心包声明零运行依赖。
- OCR/解析：README 没有宣称证据原件 OCR 或 PDF/DOCX 页级解析；重点是用户结构化输入和本地数据/模板。
- 时间线/证据：`timeline.mjs` 对 ISO `YYYY-MM-DD` 事件排序并保留来源字符串，错误日期进入 reminder；证据 Agent 输出目录、证明目的、原始载体、风险和补强。其时间线会丢弃模糊/月份级日期，无法直接满足本项目日期精度要求。
- 文书：模板生成仲裁申请书、证据目录、法援咨询摘要，并导出 Markdown/HTML/`.doc` 草稿；强调提交前人工复核。
- Agent/Skill：三个角色文件（intake/evidence/document drafter）和九个细分 Skills；外部模型是可选项，发送前要求用户勾选并展示脱敏摘要。
- 最近维护：默认分支头为 2026-07-04；仓库创建于 2026-06-07，近期活跃但历史短。
- 许可证：AGPL-3.0-or-later。
- 敏感信息：隐私文档和 UI 提醒较完善；风险仍包括浏览器本地草稿、导出目录、可选外部模型、插件安装与协作者工作流。API Key 和真实材料若由用户误放到仓库/Issue 仍可能泄露。

**审计判断（推断）**

- 可借鉴：默认不依赖模型、外发前展示脱敏摘要并二次确认、专业人士复核边界、可测试的确定性计算器、细粒度 Skills。
- 不适合继承：当前数据模型较扁平，没有页/区域级来源、冲突组、确认状态机、持久数据库和完整 OCR；严格 ISO 时间线会错误排除“某月/约某日”。
- 是否引用代码：否。AGPL 网络交互源代码提供义务可能影响本项目分发策略；若未来考虑代码复用，须先作整体许可兼容评估，不能将片段直接混入宽松许可代码库。

### 4. CaseMark/evidence-triage-OSS

来源：[仓库](https://github.com/CaseMark/evidence-triage-OSS)、[README](https://github.com/CaseMark/evidence-triage-OSS/blob/main/README.md)、[LICENSE](https://github.com/CaseMark/evidence-triage-OSS/blob/main/LICENSE)、[package.json](https://github.com/CaseMark/evidence-triage-OSS/blob/main/package.json)、[环境变量样例](https://github.com/CaseMark/evidence-triage-OSS/blob/main/.env.example)、[证据类型](https://github.com/CaseMark/evidence-triage-OSS/blob/main/lib/types/evidence.ts)、[默认分支头提交](https://github.com/CaseMark/evidence-triage-OSS/commit/37222f27e2169d7f1c40c2b73fcb7f42c51dc073)。

**核验事实**

- 可访问性/来源：公开、未归档，是 `CaseMark/casedotdev-starter-app` 的 fork。
- 实际用途：诉讼证据批量上传、OCR、AI 分类、标签、混合语义检索和 gallery/list/timeline 视图。
- 技术栈：Next.js 16 App Router、React 19、TypeScript、Tailwind/Shadcn、Vitest、PDF.js；Case.dev Vault/LLM、Neon PostgreSQL、Vercel Blob。
- OCR/解析：Vault 提供 OCR、文本提取和向量索引；`.env.example` 明确 OCR 需要 `CASE_API_KEY` 与 `BLOB_READ_WRITE_TOKEN`。
- 证据模型：类别、标签、相关度、提取文本、摘要、检测日期、处理状态、缩略图、Vault 文档引用；适合 UI 原型，但缺少证据编号、SHA-256、页/区域坐标、原始/机器/确认事实分层、确认状态和审计链。
- 时间线：有 timeline 视图和 `dateDetected`，未见支持日期精度、人工确认、冲突或多来源事实合并的正式 Timeline 模型。
- 文书/Agent：没有劳动仲裁文书生成主线；仓库 `skills/` 主要是开发/接入说明，分类与摘要由 Case.dev LLM 完成，不是案件 Agent 编排。
- 最近维护：默认分支头为 2026-01-29；检索日距该提交近 6 个月。
- 许可证：Apache-2.0。
- 敏感信息：法律证据、OCR 文本、向量、摘要和元数据需上传 Case.dev/Vercel/Neon；这是本项目“默认本地”目标的重大数据出境/第三方处理风险。API Key/Blob Token 也是高价值秘密。

**审计判断（推断）**

- 可借鉴：证据多视图、处理状态、筛选、标签、语义+关键词检索和批量上传交互。
- 不适合继承：核心 OCR/存储/数据库/LLM 都绑定云服务，无法作为离线基线；其证据结构不能支撑司法级来源回链和人工确认。
- 是否引用代码：否。Apache-2.0 原则上允许有条件复用，但未来若引用必须保留许可证/版权/归属通知、标注修改，并检查是否存在 NOTICE；目前只参考交互和抽象。

### 5. Azhu9701/Mock-Court

来源：[仓库](https://github.com/Azhu9701/Mock-Court)、[README](https://github.com/Azhu9701/Mock-Court/blob/main/README.md)、[根 LICENSE](https://github.com/Azhu9701/Mock-Court/blob/main/LICENSE)、[环境变量样例](https://github.com/Azhu9701/Mock-Court/blob/main/.env.example)、[本地 Compose](https://github.com/Azhu9701/Mock-Court/blob/main/docker-compose.local.yml)、[OCR 实现](https://github.com/Azhu9701/Mock-Court/blob/main/rust/api/src/ocr.rs)、[默认分支头提交](https://github.com/Azhu9701/Mock-Court/commit/48c49b8237c8cfc30e613abc6c1e2d4f410706ba)。

**核验事实**

- 实际用途：让仲裁法官、原告律师、被告律师、专家证人、劳动者之声等多个角色并行庭审、质证与说理，强调暴露论证盲区。
- 技术栈：Rust 2021 workspace、Axum/WebSocket、SQLite、Next.js 16/React 19、Docker/Caddy/SearXNG；有 archive/audit/cost tracking 模块。
- OCR：Rust API 把临时图片传给本机 `tesseract`；有语言参数白名单，但未显示版面区域、PDF 分页、置信度或 OCR 人工确认状态。
- 时间线/证据/文书：UI 有 session timeline，后端有会话归档；并非劳动案件证据台账或正式文书流水线。
- Agent/Provider：多角色并行/辩论/接力/单角色等模式；支持 LM Studio 本地模型，以及 OpenAI、DeepSeek、Claude 或统一中继；SearXNG 可本地搜索。
- 最近维护：默认分支头为 2026-06-18；GitHub 元数据的 `pushedAt` 更晚，但默认分支没有更晚提交，因此不能据此认定代码在 7 月持续维护。
- 许可证：README 顶部显示 MIT 徽章，但根 LICENSE 实际为“AGPLv3 + 依据第 7 节增加的非剥削集体用途、禁军工、禁监控资本主义、禁规模化数据抽取、保留运行横幅等限制”。GitHub 也识别为 `Other`。
- 敏感信息：可完全本地使用 LM Studio/Tesseract，但可选云 Provider/中继和搜索会外发案件内容；会话归档、成本记录、SQLite 和 Docker volume 会长期保存材料；生产部署若开放网络需额外认证、加密、保留期和删除机制。

**审计判断（推断）**

- 可借鉴：对抗式复核、不同角色独立立场、第二意见/盲点暴露、调用成本与审计记录。
- 不适合继承：角色辩论不能替代证据确认和法律依据核验；让多个模型接触完整证据会放大外发面与幻觉聚合风险。
- 是否引用代码：否，且在许可证书面澄清前不得复制。根 LICENSE 的附加用途限制可能与 AGPLv3 第 7 节允许的附加条款范围、OSI 开源定义及本项目分发目标冲突；README 的 MIT 表述也与法律文本直接矛盾。

### 6. Clukay-Fun/feishu-opencode-bridge

来源：[仓库](https://github.com/Clukay-Fun/feishu-opencode-bridge)、[README](https://github.com/Clukay-Fun/feishu-opencode-bridge/blob/main/README.md)、[根 LICENSE](https://github.com/Clukay-Fun/feishu-opencode-bridge/blob/main/LICENSE)、[package.json](https://github.com/Clukay-Fun/feishu-opencode-bridge/blob/main/package.json)、[数据流与隐私](https://github.com/Clukay-Fun/feishu-opencode-bridge/blob/main/docs/privacy-and-data-flow.md)、[劳动工作流分层](https://github.com/Clukay-Fun/feishu-opencode-bridge/blob/main/docs/modules/labor-skill-workflows.md)、[默认分支头提交](https://github.com/Clukay-Fun/feishu-opencode-bridge/commit/a9fb3298a50a8fa9314ee9e06468b5c4eba6727a)。

**核验事实**

- 实际用途：把本地 OpenCode 运行时接入飞书私聊/群聊/话题，提供会话窗口、权限确认、过程卡、知识库、合同、案件、发票和劳动争议工作台。
- 技术栈：Node.js 20+、TypeScript、Zod、Vitest、Lark SDK、WebSocket、better-sqlite3、docxtemplater、Mammoth、pdf-parse、XLSX；Python 辅助文档管线含 python-docx、PyMuPDF4LLM、Docling。
- OCR/文件解析：统一 document-pipeline 处理 PDF、DOCX、图片、TXT/MD、HTML 等；隐私文档称默认本地 Tesseract，外部 MinerU/PaddleOCR-VL 仅在显式开启后使用。
- 时间线/证据：`evidence-extract`、`evidence-ledger`、`timeline-build`、`workbench-generate`、`case-workflow` 已落地；证据台账字段包括类型、证明事实、支持方向、证明力、风险、状态，并可同步飞书 Base。
- 文书：合同模板、docxtemplater/Python 编辑与渲染、劳动案件工作台、飞书文档与白板；定位为律师复核底稿而非最终法律意见。
- Agent/Provider：OpenCode Skills、Runtime Module、可扩展业务模块；Provider 由 OpenCode 配置，扩展在启动期作为受信本地代码加载，无沙箱。
- 最近维护：默认分支头为 2026-05-12（0.2.2）；README 声称 72 个测试文件、622 个测试通过，但本审计未运行该仓测试，故只记录为上游声明。
- 许可证：README 末尾写“MIT”，但根 LICENSE 为 Apache-2.0（含 Copyright 2025 Clukay_Fun）；GitHub 元数据也识别为 Apache-2.0。
- 敏感信息：飞书消息、Base、OpenCode Provider、可选外部 OCR均构成外部处理面；本地还保存日志、SQLite、会话映射和断点。其隐私文档明确外部扩展不是沙箱、完整日志不适合真实案件，这是重要风险提示。

**审计判断（推断）**

- 可借鉴：Runtime/领域/共享 workflow 分层、权限确认、处理过程卡、证据台账、断点恢复、硬依据/软参考分级、默认本地 OCR 和数据流自检。
- 不适合继承：飞书是云依赖且不适合作为本项目默认存储；受信扩展无沙箱；证明力字段仍需避免伪精确化；OpenCode/飞书耦合不应进入核心域。
- 是否引用代码：否。尽管根 Apache-2.0 通常允许有条件复用，README 许可错误必须先由上游澄清；未来任何复用需以根 LICENSE 为准、保留通知并逐文件确认版权来源。

## 横向合规与安全风险矩阵

| 风险 | 严重度 | 受影响仓库 | 本项目控制建议 |
|---|---:|---|---|
| 许可不明/自相矛盾 | 高 | Mock-Court、feishu bridge；Partlawyer 的嵌套资产 | 默认不复制；建立逐文件来源清单；必要时取得书面许可或律师复核 |
| 强 copyleft/非标准使用限制 | 高 | worker-aid、labor_rights_skills、Mock-Court | 只做 clean-room 流程参考；不把代码/模板/提示词混入本项目 |
| 真实证据上传第三方云 | 高 | evidence-triage、feishu bridge、所有可选云 Provider | 本地默认；显式逐次同意；最小化/脱敏；列明处理者、区域、保留和删除策略 |
| OCR/模型结果被当作事实 | 高 | 六仓均有不同程度风险 | 四层事实模型；OCR 原文、页码、区域坐标；只有用户确认事实进入正式导出 |
| 模糊日期被错误归一/丢弃 | 中高 | worker-aid；其他仓未见明确精度模型 | 保存 exact/month/year/approximate/unknown，不补造日值 |
| 日志、浏览器存储、SQLite、导出残留 | 高 | worker-aid、Mock-Court、feishu bridge、Partlawyer | 加密/访问控制、脱敏日志、保留期、可验证删除、导出水印与审计 |
| 模型/声音/人物资产权利 | 中高 | Partlawyer-LAA | 分离代码许可、模型许可、声音/肖像授权，默认不引入数字人/克隆声音 |
| 扩展/插件供应链 | 高 | feishu bridge、worker-aid | 签名/哈希、最小权限、隔离进程、禁止默认执行未知插件 |

## 对本项目的采用建议

1. 采用 clean-room 方式自行实现：记录“借鉴了何种抽象”，不复制具体代码、提示词、文案、模板和测试夹具。
2. 优先采用 `worker-aid-agent` 的人工复核/外发确认原则、`feishu-opencode-bridge` 的工作流分层、`evidence-triage-OSS` 的证据交互、`Mock-Court` 的对抗审查思想。
3. 明确不继承：云端证据存储默认值、数字人/语音克隆、严格 ISO 日期限制、未经确认的 OCR 进入正式文书、无法追踪来源的“可信度分数”。
4. 在任何代码复用前重新核验目标提交与许可证；本报告是 2026-07-22 的快照，不替代律师对具体复用方案的法律意见。
