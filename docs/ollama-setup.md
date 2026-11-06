# Ollama 配置

LLM 默认关闭，基础闭环不依赖模型。

```env
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=qwen3:8b
LLM_API_KEY=
```

启用前在 provider 页面确认模型位于本机，并阅读将发送的字段。若使用远程 OpenAI-compatible endpoint，材料将离开本机；应先脱敏并核对服务商保留政策。模型不可用时系统显示降级，不返回 mock 分析。

