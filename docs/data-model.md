# 数据模型

核心实体为 Case、Party、Evidence、EvidencePage、EvidenceRegion、ExtractedFact、TimelineEvent、WageRecord、Claim、DocumentDraft 与 AuditLog。

## 关键不变量

- 所有案件资源必须携带 `case_id`，资源接口从资源反查案件归属。
- Evidence 的 `sha256` 在同一案件内唯一；原文件删除与数据库级联在同一删除工作流中完成。
- ExtractedFact 的机器值不可被用户修正覆盖；有效值按 `user_corrected_value ?? object_value` 解析。
- 正式派生数据查询固定过滤 `review_status = user_confirmed`。
- 时间精度独立于日期值，`month`、`year`、`approximate`、`unknown` 不补造为某一天。
- 金额以 Decimal/NUMERIC 保存，API 输出字符串，避免 JSON 浮点误差。
- DocumentDraft 版本在 `(case_id, document_type)` 内单调递增，保存事实与证据快照。

## 删除语义

案件删除先验证 owner scope，收集并校验案件存储目录位于配置的 storage root 内，再删除数据库记录和文件。失败时返回可审计错误，不对任意计算路径执行递归删除。

