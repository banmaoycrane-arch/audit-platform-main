# 多 Agent 与 CLI 执行型助手后期规划

## Summary

本规划不是要颠倒或替代当前“前端表单输入 → API 请求 → 后端鉴权 → 后端模块执行”的模式，而是在同一套执行标准下新增另一条入口路径：用户可以继续走传统前端页面，也可以通过“自然语言 + 原始文件 + 业务上下文 → Agent 理解任务 → 通过受控 CLI/API 工具调用后端 → 生成可复核结果”的多 Agent 工作模式。

财务视角理解：

- 现在的前端页面相当于“人工填单、人工点流程”。
- 后期 Agent 不只是知识库问答，而是“具备岗位角色和权限边界的电子助理”。
- Agent 可以代替用户完成重复性的录入、查询、导入、校验、生成草稿等操作。
- 但凭证入账、期间结账、审计结论确认等高风险动作仍应保留人工复核或授权确认。

技术视角目标：

- 保留现有前端和后端业务模块，不推倒重来。
- 传统前端路径与 Agent 路径共享同一套后端业务规则、权限校验、数据校验和审计日志。
- 人工用户执行、CLI 命令执行、Agent 自动执行都必须统一留痕，便于事后审计定位问题、还原过程和划分责任。
- Agent 所有后端接口必须前置鉴权；无论是页面导航型 Agent 还是执行型 Agent，都不能存在匿名调用的业务入口。
- 新增 Agent 执行层，作为与前端页面并列的“受控执行入口”，不是绕过前端和后端规则的特殊通道。
- Agent 通过后端暴露的白名单工具/API 执行业务动作，而不是直接绕过权限访问数据库。
- Agent 权限需要绑定用户、团队、账簿、项目和业务角色，并通过多 Agent 分工适配真实人员管理。
- 模型供应方应可配置，支持云端 LLM API 与本地轻量模型按环境替换；模型不可用时可回退到规则识别和受控流程。

---

## Current State Analysis

### 1. 当前请求模式

当前系统主链路已经形成：

```text
前端 React 页面
  ↓
frontend/src/api/client.ts 统一 fetch 请求
  ↓
Authorization: Bearer <token>
  ↓
FastAPI 路由
  ↓
后端 service 层
  ↓
数据库 / 文件 / 向量服务
```

已确认的关键文件：

- 前端 API 统一入口：`frontend/src/api/client.ts`
- 后端路由注册入口：`backend/app/main.py`
- 后端鉴权依赖：`backend/app/core/dependencies.py`
- 当前 Agent 路由：`backend/app/api/routes_agent.py`
- 当前 Agent 服务：`backend/app/services/agent_service.py`
- 当前 Agent 页面：`frontend/src/pages/AgentChatPage.tsx`

### 2. 当前 Agent 能力

当前 Agent 已经可以：

- 接收用户自然语言消息。
- 识别记账导入、审计流程、报告导出、基础资料、期间结账等意图。
- 配置轻量 LLM 时优先调用模型。
- 模型不可用时回退规则识别。
- 返回建议路径和步骤建议。

但当前 Agent 仍属于“导航型助手”：

```text
用户说一句话
  ↓
Agent 判断意图
  ↓
返回建议页面和步骤
  ↓
用户仍然要自己进入页面手工操作
```

当前尚未具备：

- Agent 权限模型。
- 多 Agent 角色分工。
- Agent 工具调用白名单。
- Agent 执行任务状态机。
- Agent 以 CLI/API 方式代替前端表单执行任务。
- Agent 执行日志、审批流、回滚与复核机制。

### 3. 当前权限基础

已有基础能力：

- 用户模型：`backend/app/models/user.py`
- 账簿模型：`backend/app/models/ledger.py`
- JWT 鉴权：`backend/app/core/dependencies.py`
- 账簿上下文：`X-Ledger-Id` 或 `current_user.last_ledger_id`
- 账簿权限校验：`ledger_management_service.user_has_ledger_access(...)`

重要风险与调整方向：

- `backend/app/api/routes_agent.py` 当前没有强制后端鉴权依赖。
- 后续必须把 Agent 接口级鉴权作为前置依赖先补齐。
- 鉴权逻辑不应因为“导航型 Agent”或“执行型 Agent”而分裂；页面导航、任务规划、工具执行都应复用同一套 `get_current_user`、账簿权限和角色权限逻辑。
- Agent 不能只依赖前端页面保护，否则可以被绕过直接请求后端接口。

---

## Proposed Changes

### 总体架构原则：一个执行标准，两条入口路径

后期系统应形成“双入口、单标准”的架构：

```text
入口 A：传统前端页面
用户手工选择菜单、填写表单、上传文件、点击执行

入口 B：Agent 自然语言任务台
用户用自然语言说明目标，上传原始文件，Agent 生成计划并调用受控工具

共同执行标准：
后端接口级鉴权 → 用户身份 → 执行来源识别（人工/CLI/Agent）→ 账簿权限 → Agent角色/人员角色 → 业务规则 → 数据校验 → 风险分级 → 人工确认 → 全路径审计留痕
```

因此，Agent 路径的定位不是“比前端权限更高的超级通道”，而是“用自然语言驱动同一套后端能力的另一种操作方式”。

落地时应坚持：

1. 同一业务动作只保留一套后端 service 逻辑。
2. 前端页面、CLI 命令和 Agent 工具都调用同一套 service。
3. 权限、校验、审计日志放在后端统一执行，不能分散在前端或提示词里。
4. 留痕不是 Agent 专属要求，而是人工页面、CLI、Agent 三种执行路径的共同要求。
5. Agent 接口级鉴权是基础前提，导航、规划、执行都必须鉴权。
6. Agent 可以提升效率，但不能降低复核标准。
7. 若传统前端路径需要人工确认，Agent 路径也必须人工确认。

### Phase 1：把 Agent 从“导航助手”升级为“受控任务入口”

目标：Agent 仍不直接改账，但开始具备任务识别、任务创建、任务状态跟踪能力。

#### 1. 修改 `backend/app/api/routes_agent.py`

What：

- 为 `/api/agent/chat` 增加 `Depends(get_current_user)`。
- 根据需要增加 `Depends(get_current_ledger)`。
- 新增任务规划接口，例如：
  - `POST /api/agent/tasks/plan`
  - `GET /api/agent/tasks/{task_id}`

Why：

- Agent 后期会接触财务数据，必须从第一步就绑定真实登录用户和账簿。
- 任务规划和任务执行分开，避免模型一句话就直接改账。

How：

- 现有 `chat_with_agent(message)` 保留为意图理解能力。
- 新增“计划结果”结构，返回：任务类型、涉及模块、预估动作、需要用户确认的高风险点。

#### 2. 新增或扩展 `backend/app/services/agent_service.py`

What：

- 保留现有意图识别。
- 增加任务规划函数，例如：
  - `plan_agent_task(message, user_id, ledger_id)`
- 输出结构化计划：
  - `task_type`
  - `agent_role`
  - `required_inputs`
  - `allowed_tools`
  - `approval_required`
  - `steps`

Why：

- 先让 Agent 学会“列计划”，再让 Agent 执行。
- 财务工作中，计划相当于“审计程序/记账处理方案”，需要可复核。

How：

- 短期仍可使用规则 + LLM。
- 不直接调用导入、结账、报表等业务服务。
- 只返回计划和下一步建议。

#### 3. 修改 `frontend/src/pages/AgentChatPage.tsx`

What：

- 将页面文案从“系统导航助手”升级为“任务规划助手”。
- 展示 Agent 规划出的任务步骤、所需资料、是否需要人工确认。
- 暂不提供一键执行高风险任务。

Why：

- 用户需要理解 Agent 准备做什么。
- 先培养“看计划再确认”的使用习惯。

How：

- 继续复用当前聊天页面。
- 在现有 `steps` 基础上增加任务计划卡片。

---

### Phase 2：建立 Agent 权限与角色模型

目标：明确不同 Agent 能做什么、不能做什么，并与用户权限、账簿权限、人员管理、业务风险等级绑定。

这里的“Agent 角色”不是替代人员权限，而是服务于人员管理：

```text
登录用户 / 所属团队 / 所属账簿 / 项目角色
  ↓
系统判断该用户可启用哪些 Agent
  ↓
Agent 再根据自身角色限制可调用工具
  ↓
执行同一套后端权限与业务校验
```

也就是说，Agent 是“被人员授权使用的工作助手”，不是独立于人员权限之外的新主体。

#### 1. 新增 Agent 角色配置

建议角色：

| Agent 角色 | 财务岗位类比 | 允许动作 | 禁止动作 |
| --- | --- | --- | --- |
| `navigation_agent` | 系统引导员 | 解释、导航、建议路径 | 操作数据 |
| `accounting_assistant_agent` | 记账助理 | 导入资料、生成分录草稿、做勾稽检查 | 直接入账、结账 |
| `audit_assistant_agent` | 审计助理 | 执行审计测试、整理风险发现、生成底稿草稿 | 直接确认审计结论 |
| `report_agent` | 报表助理 | 生成试算表、资产负债表、利润表、报告草稿 | 修改基础账务数据 |
| `admin_agent` | 系统管理员助理 | 查询团队、账簿、用户配置 | 越权访问其他账簿 |

建议实现位置：

- 简单阶段：在 `backend/app/services/agent_service.py` 中用配置字典维护。
- 稳定阶段：新增数据库表维护 Agent 角色、工具权限、风险等级。

Why：

- 多 Agent 本质上类似“不同岗位人员”。
- 会计实务中制单、审核、记账、结账、审计复核不能混为一个无限权限角色。

#### 2. 设计 Agent 权限维度

权限判断建议至少包含：

```text
用户身份 user_id
  + 团队 team_id
  + 账簿 ledger_id
  + 项目 project_id
  + Agent 角色 agent_role
  + 工具权限 tool_permission
  + 操作风险等级 risk_level
```

高风险动作示例：

- 提交正式凭证。
- 删除或覆盖导入数据。
- 期间损益结转。
- 期间结账 / 反结账。
- 确认审计发现为最终结论。
- 导出正式审计报告。

这些动作应设置为：

```text
Agent 可生成草稿或建议
  ↓
用户复核确认
  ↓
后端再次鉴权
  ↓
业务服务执行
  ↓
写入审计日志
```

---

### Phase 3：建立 CLI / Tool 执行层

目标：让 Agent 不再模仿前端点击，而是通过后端允许的“工具命令”执行业务。

#### 1. 新增 Agent 工具注册表

建议新增文件：

- `backend/app/services/agent_tool_registry.py`

What：

- 定义 Agent 可以调用的工具白名单。
- 每个工具映射到一个已有后端 service 函数或受控 API 动作。

示例工具：

```text
upload_source_file
create_import_job
process_import_job_sync
generate_entry_drafts
run_audit_tests
generate_trial_balance
generate_balance_sheet
generate_income_statement
export_audit_report
```

Why：

- Agent 不能任意执行后端代码。
- 白名单工具类似“岗位授权清单”。
- 便于审计追踪：谁让哪个 Agent 在哪个账簿执行了哪个工具。

How：

- 每个工具定义：名称、说明、入参 schema、所需权限、风险等级、是否需要人工确认。
- Agent 调用前先校验权限，再执行。

#### 2. 新增 CLI 命令接口层

建议新增文件：

- `backend/app/services/agent_cli_service.py`

说明：这里的 CLI 不一定是传统本地命令行窗口，而是“命令式工具接口”。Agent 向后端提交结构化命令，例如：

```json
{
  "command": "process_import_job_sync",
  "args": {
    "job_id": 12
  },
  "ledger_id": 3,
  "approval_token": "..."
}
```

Why：

- 前端表单是“页面操作模式”。
- CLI/Command 是“任务执行模式”。
- Agent 更适合生成结构化命令，而不是模拟鼠标点击。

How：

- 初期只支持低风险查询类和草稿类命令。
- 对高风险命令返回“需要确认”，不直接执行。

#### 3. 新增 Agent 执行 API

建议新增或扩展：

- `backend/app/api/routes_agent.py`

接口草案：

```text
POST /api/agent/tasks/plan        生成任务计划
POST /api/agent/tasks             创建 Agent 任务
POST /api/agent/tasks/{id}/run    执行低风险步骤
POST /api/agent/tasks/{id}/approve 用户确认高风险步骤
GET  /api/agent/tasks/{id}        查询任务状态
POST /api/agent/tasks/{id}/cancel 取消任务
```

Why：

- 多步骤任务不能只靠一次 HTTP 请求完成。
- 用户需要看到任务进度、失败原因、已执行步骤。

How：

- 阶段初期可以同步执行。
- 后期可接入 Redis/Celery/RQ 等后台任务队列。

---

### Phase 4：建立统一执行留痕与审计日志

目标：不仅 Agent 的每一步要可追溯，人工用户在前端页面执行、CLI 命令执行、Agent 自动执行都应纳入同一套留痕体系，满足审计事后定位问题、还原过程和划分责任的要求。

财务审计视角：

- 谁发起了动作。
- 通过什么入口发起：人工页面、CLI、Agent。
- 在哪个团队、账簿、项目、期间内执行。
- 执行前数据是什么状态。
- 执行了哪些步骤。
- 哪些步骤由模型建议，哪些步骤由人确认。
- 执行后数据发生了什么变化。
- 如果结果错误，能定位到责任链条：发起人、确认人、Agent 角色、工具、模型输出、后端服务。

#### 统一留痕对象

建议把执行来源统一抽象为：

```text
execution_source = manual_ui | cli_command | agent_auto | agent_assisted
```

含义：

| 来源 | 含义 | 示例 |
| --- | --- | --- |
| `manual_ui` | 人工用户通过前端页面执行 | 用户点击“结账”按钮 |
| `cli_command` | 通过受控命令接口执行 | 管理员运行导入处理命令 |
| `agent_auto` | Agent 在授权范围内自动执行低风险动作 | 查询风险列表、生成报表预览 |
| `agent_assisted` | Agent 生成计划或草稿，用户确认后执行 | 生成凭证草稿后由用户确认提交 |

#### 统一留痕字段

建议所有关键业务动作都记录：

```text
trace_id                  单次业务动作追踪编号
request_id                单次请求编号
execution_source          执行来源：manual_ui / cli_command / agent_auto / agent_assisted
user_id                   发起用户
confirmed_by_user_id      确认用户，高风险动作必填
team_id                   团队
ledger_id                 账簿
project_id                项目
accounting_period_id      会计期间
agent_role                Agent 角色，非 Agent 动作为空
agent_task_id             Agent 任务ID，非 Agent 动作为空
tool_name                 工具或业务动作名称
service_name              实际后端 service 名称
business_object_type      业务对象类型，例如 voucher/import_job/audit_finding
business_object_id        业务对象ID
risk_level                操作风险等级
approval_required         是否需要确认
approval_id               确认记录ID
input_summary             输入摘要，不保存敏感明文全文
before_snapshot_hash      执行前快照哈希
after_snapshot_hash       执行后快照哈希
model_provider            模型供应方，非模型动作可为空
model_name                模型名称，非模型动作可为空
model_prompt_hash         提示词哈希，避免直接暴露敏感数据
model_output_hash         模型输出哈希
status                    success / failed / cancelled
error_message             失败原因
created_at                发生时间
```

#### 留痕粒度

建议分三层：

1. 操作级日志：记录一次业务动作，例如“生成分录草稿”。
2. 步骤级日志：记录多步骤任务中的每一步，例如“解析文件、匹配科目、生成分录、借贷平衡校验”。
3. 数据变更级日志：记录关键对象前后变化，例如凭证状态、期间状态、审计发现状态。

#### 与现有模块的关系

- 前端页面操作：在对应 API 路由或 service 执行前后写日志。
- CLI 命令操作：CLI 服务提交命令时必须携带用户身份、来源和账簿上下文。
- Agent 操作：Agent 任务、工具调用、人工确认、模型输出摘要都写入日志。

也就是说，留痕能力应沉到后端统一服务层，而不是只在 Agent 页面做显示。

#### 1. 新增任务与统一日志表

建议新增模型文件或扩展现有模型：

- `backend/app/models/agent.py`：Agent 任务、步骤、确认记录。
- `backend/app/models/execution_audit.py`：统一执行留痕，覆盖人工页面、CLI、Agent。

建议表：

```text
agent_tasks
agent_task_steps
agent_approvals
execution_audit_logs
execution_audit_steps
data_change_logs
```

其中 `agent_tasks` 侧重记录 Agent 任务本身，核心字段建议包括：

```text
task_id
user_id
team_id
ledger_id
project_id
agent_role
task_type
status
input_message
input_files
planned_steps
current_step
created_at
updated_at
```

`execution_audit_logs` 侧重记录所有执行路径的统一审计轨迹，字段应以“统一留痕字段”章节为准。

Why：

- Agent 自动执行后，必须知道“谁发起、在哪个账簿、执行了什么、结果是什么”。
- 人工用户和 CLI 执行同样需要知道“谁执行、通过什么入口执行、影响了什么数据”。
- 财务系统不能只保存最终结果，还要保存过程。

#### 2. 写入审计日志

人工页面、CLI、Agent 每次执行关键业务动作时都应记录。Agent 执行每个工具时还需要额外记录 Agent 任务、模型和人工确认信息：

```text
执行人：用户ID
执行角色：Agent角色
账簿：ledger_id
工具：tool_name
参数摘要：args_summary
执行前状态：before_snapshot
执行后状态：after_snapshot
是否人工确认：approval_id
执行结果：success / failed
错误原因：error_message
```

Why：

- 这相当于系统操作日志和审计轨迹。
- 出现财务差错时可以回溯 Agent 是如何产生结果的。

---

### Phase 5：模型供应方可配置与可替换

目标：前端 Agent 配置的大模型不绑定单一供应商，后端统一适配云端 API 和本地轻量模型。

#### 1. 模型配置原则

模型能力应作为“可替换组件”，而不是写死在 Agent 业务逻辑里。

支持形态：

| 模型形态 | 适用场景 | 示例 |
| --- | --- | --- |
| 云端 LLM API | 需要较强理解能力、可接受外部 API 调用 | OpenAI-compatible API、其他云模型服务 |
| 本地轻量模型 | 数据敏感、内网部署、低成本推理 | 本地 OpenAI-compatible 服务、Ollama/vLLM/llama.cpp 类服务 |
| 规则兜底 | 模型不可用、基础导航、确定性流程 | 当前 `agent_service.py` 的规则识别 |

#### 2. 后端统一模型适配

建议继续沿用现有 `backend/app/services/llm_client_service.py` 的 OpenAI-compatible 思路，逐步扩展配置：

```text
AI_PROVIDER      模型供应方标识
AI_BASE_URL      云 API 或本地模型服务地址
AI_API_KEY       云 API 密钥；本地模型可为空或使用内网密钥
AI_MODEL         模型名称
AI_TIMEOUT       调用超时时间
AI_MAX_TOKENS    单次返回长度限制
```

Why：

- 前端不保存 API Key，避免泄露。
- 后端统一调用模型，便于审计和权限控制。
- 云模型和本地模型只换配置，不改 Agent 业务逻辑。

#### 3. 前端配置边界

前端可以提供“模型配置管理页面”或“Agent 配置页面”，但只应提交配置意图或由管理员维护配置，不应把密钥长期暴露给普通浏览器页面。

建议分级：

```text
普通用户：选择可用 Agent，不直接配置模型密钥
团队管理员：选择团队默认模型供应方
系统管理员：维护 AI_BASE_URL / AI_API_KEY / AI_MODEL 等敏感配置
```

#### 4. 模型与权限的关系

模型只负责理解、规划、生成建议；最终能否执行仍由后端权限决定。

```text
模型判断：用户想做什么
权限系统判断：用户和 Agent 是否允许做
业务服务判断：数据是否符合财务规则
人工复核判断：高风险事项是否确认
```

因此，即使更换更强的模型，也不能绕过鉴权、账簿权限、工具白名单和人工确认。

---

### Phase 6：多 Agent 协同编排

目标：从一个通用 Agent 演进为多个专业 Agent 协同处理复杂任务。

建议采用“主控 Agent + 专业 Agent”的结构：

```text
用户自然语言
  ↓
OrchestratorAgent 总调度
  ↓
识别任务类型、拆解步骤、分配 Agent
  ↓
AccountingAgent / AuditAgent / ReportAgent / DataImportAgent / PermissionAgent
  ↓
Tool Registry 调用后端工具
  ↓
结果汇总、复核、输出
```

#### Agent 分工建议

| Agent | 职责 | 优先级 |
| --- | --- | --- |
| `orchestrator_agent` | 理解用户目标、拆任务、调度其他 Agent | 高 |
| `permission_agent` | 判断用户、账簿、项目、工具权限 | 高 |
| `data_import_agent` | 处理原始文件、导入任务、解析结果 | 高 |
| `accounting_agent` | 生成分录草稿、做借贷平衡、辅助凭证复核 | 高 |
| `audit_agent` | 执行审计测试、生成风险发现草稿 | 中 |
| `report_agent` | 生成报表和报告草稿 | 中 |
| `knowledge_agent` | 解释准则、政策、系统帮助 | 中 |

重要原则：

- `permission_agent` 或统一权限服务必须先于工具执行。
- `accounting_agent` 只能生成草稿，不能绕过复核直接最终入账。
- `audit_agent` 可以形成审计发现草稿，但最终审计结论需要人工确认。

---

## Recommended Implementation Order

### 第一阶段：安全与留痕补底座

1. 给所有 Agent 后端接口补登录鉴权，包括导航、聊天、任务规划和后续执行接口。
2. 复用同一套 `get_current_user`、账簿权限和角色权限逻辑，不为 Agent 单独开匿名或特殊权限通道。
3. 设计统一执行留痕结构，覆盖人工页面、CLI、Agent 三种来源。
4. 明确 Agent 当前只能导航和规划，不能执行改账动作。
5. 增加 Agent 返回结构：任务类型、所需资料、风险等级、是否需要人工确认。
6. 前端展示任务计划卡片。

### 第二阶段：低风险工具调用

优先开放只读或草稿类工具：

- 查询账簿概览。
- 查询导入任务状态。
- 查询分录列表。
- 查询风险列表。
- 生成审计测试计划草稿。
- 生成分录草稿但不入账。
- 生成报表预览。

### 第三阶段：半自动执行业务流程

开放需要人工确认的动作：

- 上传并解析文件。
- 创建导入任务。
- 执行导入处理。
- 生成凭证草稿。
- 执行审计测试。
- 生成审计报告草稿。

### 第四阶段：高风险动作审批

对下列动作建立强制确认和审计日志：

- 提交正式凭证。
- 期间损益结转。
- 期间结账。
- 反结账。
- 删除业务数据。
- 确认审计结论。
- 导出正式审计报告。

### 第五阶段：模型配置与替换

1. 后端统一维护模型配置，支持云端 API 和本地轻量模型。
2. 前端只做受控配置入口，不直接暴露密钥给普通用户。
3. 模型不可用时，Agent 回退到规则识别和确定性流程。
4. 更换模型不改变后端权限、工具白名单和人工确认规则。

### 第六阶段：多 Agent 协同

在前面权限、工具、日志、模型配置稳定后，再拆分专业 Agent，避免一开始过度设计。

---

## Assumptions & Decisions

### 已做决策

1. 不推翻现有前端页面和后端 API。
2. Agent 是新增执行入口，不替代现有人工页面。
3. Agent 路径与前端路径必须执行同一套业务规则、权限规则、校验规则和审计规则。
4. 人工页面、CLI、Agent 自动执行都必须纳入统一留痕体系。
5. Agent 所有接口都必须鉴权，包括导航型接口和执行型接口。
6. Agent 执行动作必须走后端受控工具/API，不直接操作数据库。
7. Agent 权限必须绑定用户、账簿、团队和项目上下文，并服务于真实人员管理。
8. 高风险财务动作必须人工确认。
9. 所有关键执行动作都必须写入审计日志，支持事后定位问题、还原过程和划分责任。
10. 模型供应方可替换，支持云端 API 与本地轻量模型；模型能力不改变权限边界。

### 当前假设

1. 项目后期仍以 FastAPI 后端作为唯一可信执行层。
2. 前端仍作为用户交互入口，但逐步从“表单页面”扩展为“自然语言任务台”。
3. CLI 是后端内部的命令式工具接口，不一定要求用户打开本地命令行。
4. 原始文件上传仍通过后端存储和解析流程处理，Agent 只负责组织任务和调用工具。

### 需要后续由用户确认的业务口径

1. 哪些动作允许 Agent 自动完成？
2. 哪些动作必须人工确认？
3. Agent 的角色是否按“记账、审核、审计、报表、系统管理”划分？
4. 审计结论是否允许 Agent 草拟但必须人工最终确认？
5. 是否需要区分企业内部财务场景和会计师事务所审计场景的 Agent 权限？

---

## Verification Steps

### 规划验证

1. 检查本规划是否符合财务实务：
   - 制单、审核、记账、结账是否有权限边界。
   - 审计测试、审计发现、审计结论是否有复核边界。
   - 已结账期间是否不会被 Agent 绕过修改。
   - 人工用户、CLI、Agent 三种路径是否都能留痕并追溯责任。

2. 检查技术落地性：
   - 是否复用现有 `api/routes + services + models` 分层。
   - 是否复用现有 JWT 用户鉴权。
   - 是否复用现有账簿上下文 `X-Ledger-Id`。
   - 是否避免 Agent 直接访问数据库。

### 后续代码实施时的验证命令

后端：

```powershell
python -m pytest backend/tests
```

前端：

```powershell
pnpm --dir frontend lint
pnpm --dir frontend build
```

### 功能验收建议

1. 未登录用户调用任何 Agent 接口，包括导航聊天接口，应返回 401。
2. 无账簿权限用户调用 Agent 工具，应返回 403。
3. Agent 查询类工具可直接执行。
4. Agent 高风险工具只能生成待确认步骤，不能直接落库。
5. 用户确认后，高风险工具执行并写入日志。
6. 人工页面执行关键业务动作时，写入 `execution_source=manual_ui` 的日志。
7. CLI 执行关键业务动作时，写入 `execution_source=cli_command` 的日志。
8. Agent 自动执行或辅助执行时，写入 `execution_source=agent_auto` 或 `agent_assisted` 的日志。
9. 审计日志可以按用户、账簿、项目、期间、业务对象、Agent 任务、执行来源查询。
10. Agent 任务页面能展示：计划、步骤、执行状态、结果、失败原因。
11. 云端 LLM API 与本地轻量模型可以通过配置切换。
12. 模型不可用时，Agent 可以回退到规则识别，不影响基础导航和受控流程。
13. 更换模型后，鉴权、账簿权限、工具白名单和人工确认规则保持不变。

---

## Short Conclusion

后期方向建议不是把 Agent 做成“更聪明的聊天框”，而是把它做成“有岗位角色、有权限边界、有工具清单、有执行日志的财务工作助理”。

最稳妥的演进路线是：

```text
同一后端执行标准
  ↓
传统前端路径 + Agent 自然语言路径并行
  ↓
导航型 Agent
  → 任务规划型 Agent
  → 低风险工具执行 Agent
  → 需要人工确认的半自动 Agent
  → 支持云端/本地模型替换
  → 多 Agent 协同工作台
```

这样既能提升效率，又不会牺牲财务系统最重要的权限控制、复核控制和审计留痕。
