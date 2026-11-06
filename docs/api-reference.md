# API 参考

基础地址：`http://localhost:8000`。交互式 OpenAPI：`/docs`。

统一成功响应：

```json
{"success": true, "data": {}, "error": null, "meta": {}}
```

统一错误响应：

```json
{"success": false, "data": null, "error": {"code": "RESOURCE_NOT_FOUND", "message": "..."}, "meta": {}}
```

## 资源

- 案件：`POST/GET /api/cases`，`GET/PATCH/DELETE /api/cases/{case_id}`。
- 证据：`POST/GET /api/cases/{case_id}/evidence`，`GET/DELETE /api/evidence/{evidence_id}`。
- 处理：`POST /api/evidence/{evidence_id}/process`，`GET .../ocr`，`GET .../extractions`。
- 事实：`GET /api/cases/{case_id}/facts`，`PATCH /api/facts/{fact_id}`，`POST .../confirm|reject`。
- 时间线：`GET /api/cases/{case_id}/timeline`，`POST .../timeline/rebuild`。
- 工资：`GET/POST /api/cases/{case_id}/wages`，`PATCH /api/wages/{wage_id}`，`POST .../calculations/recalculate`。
- 请求：`GET/POST /api/cases/{case_id}/claims`，`PATCH /api/claims/{claim_id}`。
- 工作流：`POST .../gap-analysis`，`POST .../adversarial-review`。
- 文书：`POST .../documents/generate`，`GET .../documents`，`GET /api/documents/{id}`，`POST .../export`。
- 档案：`POST /api/cases/{case_id}/export`，`POST /api/cases/{case_id}/filing-pack`（生成线下立案预填 ZIP），`GET /api/cases/{case_id}/exports/{filename}`。
- 系统：`GET /api/system/health|providers|self-check`。

所有 mutation 均校验资源归属；文件上传使用 multipart，金额字段使用十进制字符串。
