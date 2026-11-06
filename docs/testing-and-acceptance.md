# 测试与验收

## 命令

```powershell
.\.venv\Scripts\python -m pytest apps/api/tests -q
Set-Location apps\web; npm test -- --run; npm run build
npm run test:e2e
```

端到端从空数据库创建虚构案件，上传真实生成的文件，运行 OCR，确认部分事实，保留未确认事实，生成时间线/工资/缺口/抗辩/文书并导出 ZIP。验收证据包括测试日志、Playwright 截图、导出文件、manifest 和 `/api/system/self-check` JSON。

2026-07-22 最终结果：后端 21/21、前端 3/3、真实 Playwright 1/1 通过，Next.js 生产构建通过；系统自检 16 项无失败。详见 `final-acceptance-report.md`。
