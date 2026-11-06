# 系统架构

## 组件

```text
Browser / Next.js 15
        |
        | JSON + multipart
        v
FastAPI modular monolith
  |-- Case / Party
  |-- Evidence / OCR Router
  |-- Fact / Timeline
  |-- Wage / Claim / Decimal Calculators
  |-- Restricted Agent Workflows
  |-- Document / Export / Safety Review
        |
        +-- SQLite (default) / PostgreSQL
        +-- private local case storage
        +-- optional Ollama / OpenAI-compatible provider
```

## 信任边界

- 浏览器输入、文件名、OCR 文本和证据正文均是不可信输入。
- 文件落盘前执行类型、大小、扩展名和路径校验。
- provider 层是唯一允许材料离开本机的边界；默认关闭。
- 文书层只接受已确认事实快照，不接受自由文本拼接的机器结论。
- 导出层重新校验归属、模板变量和敏感字段。

## 数据流

1. 上传保存原始字节和 SHA-256；重复文件返回已有证据提示。
2. parser/OCR 生成不可变原文页与区域；机器规则或 LLM 只生成候选事实。
3. 用户操作改变 review status，修正值与原机器值并存。
4. 时间线、工资和文书通过 confirmed-only 查询构建。
5. 文书生成冻结快照；安全审查通过后导出。

## 降级策略

- OCR 失败：保留文件与失败原因，开放人工原文。
- LLM 关闭：规则提取和人工事实仍可用；agent 页面显示降级。
- PostgreSQL 不可用：SQLite 保持完整单机闭环。
- PDF 转换不可用：返回明确失败，不以改扩展名伪装 PDF。

