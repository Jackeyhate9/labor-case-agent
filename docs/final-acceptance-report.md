# 最终验收报告

验收日期：2026-07-22（Asia/Shanghai）

分支：`codex/labor-case-agent`

样本：`samples/demo-case/` 中完全虚构的数据

## 结果

| 验收项 | 结果 | 证据 |
|---|---:|---|
| 后端自动化 | 21/21 通过，93% 语句覆盖率 | `python -m pytest -q --cov=app` |
| 前端单元/组件 | 3/3 通过 | `npm test -- --run` |
| 前端生产构建 | 通过 | `npm run build`，5 个路由完成编译与静态/动态构建 |
| 真实端到端 | 1/1 通过 | Playwright 驱动真实 Next.js、FastAPI、SQLite 与 RapidOCR |
| 系统自检 | 通过 | 16 项检查，0 failed；LLM/embedding 按默认配置 skipped |
| API 表面 | 36 个端点 | FastAPI 路由统计 |

端到端流程实际完成：新建案件和双方当事人、上传 `chat-01.png`、中文 OCR、事实确认、重建时间线、录入 6000/1000 元工资并得到 5000 元欠薪、缺口分析、抗辩模拟、生成 v1 仲裁申请书、ZIP 下载与系统自检。

首轮浏览器验收发现“证据缺口 → 抗辩模拟”复用了前一 mutation 的状态，导致第二次仍请求缺口接口。两个工作流改为独立 keyed 实例后复验通过。

## 实际输出

- 工作台截图：`docs/images/labor-case-workspace.png`
- 案件归档：`artifacts/demo-case/case-archive.zip`
- ZIP 大小：1,116,767 字节
- ZIP SHA-256：`6e10597c9452cbe71d9306c1ee8d7a5b59fb0eb2e34fe4aa261cda466bf4d165`

归档包含：案件说明、事实摘要、仲裁申请书草稿、证据目录、欠薪明细、时间线、待补证清单、原始证据、OCR 文本、已确认事实 JSON、时间线 JSON 和带哈希的 export manifest。原始 PNG 使用不重压缩的 ZIP 存储方式。

## 自检明细

通过：数据库连接、数据库表结构、私有存储、临时目录、DOCX/PDF/XLSX、RapidOCR、法律元数据目录、演示样本、前后端 API 契约、ZIP、文书模板与敏感日志策略。

跳过：LLM、embedding。二者默认关闭，且不影响本 MVP 的确定性核心流程。

## 未完成/降级项

- 未持久化 OCR 文本框坐标，未提供区域裁剪预览。
- 未完成证据原件的浏览器内嵌预览/独立下载入口。
- 未实现音频转写、在线仲裁提交、电子签章、生产级身份认证与多租户隔离。
- 法律目录是来源元数据，不是完整现行法全文库；所有引用和法律判断仍需人工复核。
- Docker daemon 在验收环境中未运行，因此 PostgreSQL compose 配置只做静态检查；最终动态基线为 Windows + SQLite。
