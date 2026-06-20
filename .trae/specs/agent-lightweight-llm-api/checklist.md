# Checklist

- [x] `llm_client_service.py` 已创建
- [x] 支持 OpenAI-compatible `/chat/completions`
- [x] LLM 未配置时 Agent 返回 `source="rules"`
- [x] LLM 成功时 Agent 返回 `source="llm"`
- [x] LLM 异常时 Agent 不返回 500，并回退规则型结果
- [x] Agent 返回字段包含 `source` 和 `model_available`
- [x] 前端 Agent 页面展示回答来源
- [x] 前端 Agent 页面能提示模型不可用时使用规则兜底
- [x] API Key 只在后端配置读取，未暴露给前端
- [x] `backend/tests/test_agent_llm_api.py` 覆盖主要场景
- [x] 后端相关 pytest 通过
- [x] 前端 `npm run lint` 通过
