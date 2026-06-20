# Tasks

- [x] Task 1: 新增轻量 LLM 客户端服务
  - [x] SubTask 1.1: 新增 `backend/app/services/llm_client_service.py`
  - [x] SubTask 1.2: 复用 `get_settings()` 读取 `ai_base_url`、`ai_api_key`、`ai_model`
  - [x] SubTask 1.3: 实现 OpenAI-compatible `/chat/completions` 调用
  - [x] SubTask 1.4: 设置短超时，调用失败返回降级结果而不是抛出到接口层

- [x] Task 2: 扩展 Agent 服务
  - [x] SubTask 2.1: 在 `agent_service.py` 增加系统模块上下文 prompt
  - [x] SubTask 2.2: 实现 LLM 优先、规则兜底
  - [x] SubTask 2.3: 规范化返回字段：`intent`、`confidence`、`reply`、`suggested_path`、`steps`、`source`、`model_available`
  - [x] SubTask 2.4: 保持现有规则型 Agent 行为兼容

- [x] Task 3: 扩展 Agent API
  - [x] SubTask 3.1: 修改 `backend/app/api/routes_agent.py` 调用增强后的 Agent 服务
  - [x] SubTask 3.2: 确保空消息仍返回 400
  - [x] SubTask 3.3: 不向前端暴露 `ai_api_key`

- [x] Task 4: 前端展示模型状态
  - [x] SubTask 4.1: 修改 `frontend/src/api/client.ts` 的 `AgentChatResponse` 类型
  - [x] SubTask 4.2: 修改 `frontend/src/pages/AgentChatPage.tsx`，展示回答来源 `llm/rules`
  - [x] SubTask 4.3: 当模型不可用时提示“当前使用规则兜底”

- [x] Task 5: 测试与验证
  - [x] SubTask 5.1: 新增 `backend/tests/test_agent_llm_api.py`
  - [x] SubTask 5.2: 覆盖 LLM 未配置时规则兜底
  - [x] SubTask 5.3: 覆盖 LLM 成功返回结构化结果
  - [x] SubTask 5.4: 覆盖 LLM 异常时不 500，回退规则结果
  - [x] SubTask 5.5: 运行后端相关 pytest
  - [x] SubTask 5.6: 运行前端 `npm run lint`

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 1-4
