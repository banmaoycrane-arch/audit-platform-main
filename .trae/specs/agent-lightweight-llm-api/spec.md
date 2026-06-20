# Agent 助手轻量大模型 API Spec

## Why

当前 Agent 助手是规则型意图识别，只能通过关键词判断“记账、审计、报告、基础资料、期间”等路径，难以理解用户对系统内部需求的自然语言描述。接入一个轻量 OpenAI-compatible 大模型 API，可以让 Agent 更快理解用户意图、解释系统模块、给出下一步操作建议，同时保留规则型兜底，避免模型不可用时影响主流程。

## What Changes

- 新增轻量 LLM 客户端服务，复用现有配置：
  - `ai_provider`
  - `ai_base_url`
  - `ai_api_key`
  - `ai_model`
- 扩展 Agent Chat：
  - 优先调用轻量 LLM 理解用户需求
  - LLM 不可用、未配置或调用失败时，自动回退现有规则型 Agent
- 为 Agent 提供系统内部模块上下文：
  - 记账模式 Step 1-5
  - 审计模式 Step 1-6
  - 基础资料
  - 会计期间与损益结转
  - 报表
  - 风险列表
  - EntryTag / 文档解析 / 业务循环 / 内控审计等已实现能力
- 前端 Agent 页面展示：
  - 当前回答来源：`llm` 或 `rules`
  - 模型是否可用
  - 原有建议路径与步骤建议继续保留
- 不把 API Key 暴露到前端。

## Impact

- Affected specs:
  - `summary-library`
  - `workspace-navigation-continuity`
- Affected code:
  - `backend/app/core/config.py`
  - `backend/app/services/agent_service.py`
  - `backend/app/services/llm_client_service.py`
  - `backend/app/api/routes_agent.py`
  - `backend/tests/test_agent_llm_api.py`
  - `frontend/src/pages/AgentChatPage.tsx`
  - `frontend/src/api/client.ts`

## ADDED Requirements

### Requirement: OpenAI-compatible 轻量模型调用

系统 SHALL 支持通过后端环境变量配置 OpenAI-compatible 大模型接口，并由后端代理调用。

#### Scenario: LLM 配置完整
- **WHEN** `ai_base_url`、`ai_api_key`、`ai_model` 已配置
- **THEN** Agent Chat 优先调用 LLM
- **AND** 返回结果包含 `source="llm"`

#### Scenario: LLM 未配置
- **WHEN** `ai_base_url` 或 `ai_model` 缺失
- **THEN** Agent Chat 自动使用规则型识别
- **AND** 返回结果包含 `source="rules"`

### Requirement: 系统上下文提示词

系统 SHALL 为 LLM 提供简短的系统内部能力上下文，使其知道本软件有哪些页面和流程。

#### Scenario: 用户询问“我想先导入序时簿再审计”
- **WHEN** 用户向 Agent 输入该需求
- **THEN** Agent 应能建议进入 `/audit/step/3` 或审计流程相关路径

### Requirement: 结构化返回

系统 SHALL 将 LLM 输出规范化为结构化字段：`intent`、`confidence`、`reply`、`suggested_path`、`steps`、`source`、`model_available`。

#### Scenario: LLM 返回非标准文本
- **WHEN** LLM 返回不可解析 JSON
- **THEN** 系统仍返回可展示回复
- **AND** 保留规则型建议路径作为兜底

### Requirement: 安全边界

系统 SHALL 只在后端读取大模型 API Key，前端不得保存或展示密钥。

#### Scenario: 前端请求 Agent Chat
- **WHEN** 浏览器调用 `/api/agent/chat`
- **THEN** 请求体只包含用户消息
- **AND** 不包含 `ai_api_key`

### Requirement: 可测试降级

系统 SHALL 有测试覆盖 LLM 未配置、LLM 成功、LLM 失败回退三种场景。

#### Scenario: LLM 调用失败
- **WHEN** HTTP 请求超时或返回错误
- **THEN** Agent Chat 返回规则型结果
- **AND** 不抛出 500

## MODIFIED Requirements

### Requirement: Agent Chat

现有 Agent Chat 从纯规则型意图识别修改为“LLM 优先 + 规则兜底”。返回字段保持向后兼容，新增 `source` 与 `model_available`。

## REMOVED Requirements

无。

## 财务视角说明

- 轻量模型不是替代账务规则，而是帮助用户把自然语言需求映射到系统功能。例如“我想看这个供应商有没有预付款长期未核销”应被引导到审计/业务循环/风险列表，而不是让用户自己猜菜单。
- 财务系统的确定性规则仍由后端业务服务和数据库保证；LLM 只做“理解需求、解释系统、推荐入口”。
- API Key 放在后端环境变量里，符合财务系统对凭证、客户、供应商等敏感数据的基本安全要求。