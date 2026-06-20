# 工作区需求识别、项目进度复盘与下一步动作计划

## Summary

本计划用于复盘当前工作区 `e:\projects\finance-vector-audit\wroksapce20260616` 的全部需求、实现进度和后续行动建议。项目当前已经具备较完整的前后端基础骨架、丰富的后端数据模型、多个服务层模块，以及部分已挂载 API；但各模块完成层级不一致：有些模块已做到“模型 + 服务 + API + 测试”，有些只做到“模型/服务”，有些仍停留在规范层。

从财务审计价值看，下一阶段最重要的不是继续扩展模型，而是把“审计模式真实闭环”打通：导入原始资料与被审计单位分录，执行真实审计测试，生成可复核的审计发现，并逐步把前端 mock 数据替换为真实 API 返回。

## Current State Analysis

### 1. 已识别的规范需求目录

当前 `.trae/specs` 下存在以下需求规范：

1. `accounting-period-snapshot`：会计分期、期间快照、结账、反结账。
2. `adaptive-import-engine`：自适应导入引擎。
3. `business-cycle-audit`：业务循环审计。
4. `document-parsing-engine`：原始文件解析引擎。
5. `entity-semantic-mapping`：会计主体语义映射。
6. `internal-accounting-unit`：内部核算单位与物料层级。
7. `internal-control-audit`：内控测试与风险量化。
8. `progress-review`：项目阶段复盘。
9. `summarize-requirements`：总需求梳理。
10. `summary-library`：智能摘要库与逻辑校验。
11. `transactional-design`：事务性设计。

### 2. 已识别的历史计划/复盘文档

当前 `.trae/documents` 下已有以下重要文档：

1. `agent-architecture-plan.md`：Agent 入口规划。
2. `environment-recognition-plan.md`：环境识别。
3. `finance-vector-audit-plan.md`：项目初始方案。
4. `frontend-api-fix-plan.md`：前端 API 修复计划。
5. `project-progress-status-plan.md`：项目进展状态。
6. `project-review-plan.md`：项目复盘。

### 3. 当前后端实现状态

关键入口与模块：

- `backend/app/main.py`：FastAPI 入口，已挂载 imports、entries、files、risks、accounting-periods。
- `backend/app/db/models.py`：核心 SQLAlchemy 模型文件，当前已覆盖组织、导入、分录、主体、会计期间、快照、核算单位、物料、事务、风险、业务循环、内控、合同、发票、库存单、银行流水、企业信息等模型。
- `backend/app/services`：服务层非常丰富，包含导入、解析、标签、摘要、逻辑校验、风险、AI、向量库、审计测试、业务循环、内控、主体、核算单位、会计期间、事务管理等。
- `backend/app/api`：当前 API 层相对服务层偏少，已存在 imports、entries、files、risks、accounting_periods。

### 4. 当前前端实现状态

关键入口与模块：

- `frontend/src/main.tsx`：前端入口。
- `frontend/src/App.tsx`：路由入口。
- `frontend/src/api/client.ts`：前端 API 客户端。
- `frontend/src/pages/HomePage.tsx`：模式选择首页。
- `frontend/src/pages/AccountingMode`：记账模式多步骤页面。
- `frontend/src/pages/AuditMode`：审计模式多步骤页面。

前端已经具备流程页面，但部分页面仍使用 mock 数据或模拟行为，尤其是审计测试、审计发现复核、自动生成分录等关键步骤。

## 需求模块完成度矩阵

| 模块 | 文档 | 模型 | 服务 | API | 前端 | 测试 | 当前判断 |
|---|---|---|---|---|---|---|---|
| MVP 导入/分录/风险 | 已有 | 已有 | 已有 | 已有 | 已有 | 部分已有 | 主干基本可用 |
| 自适应导入引擎 | 已有 | 部分 | 已有 | 通过导入流程间接使用 | 部分 | 待补全 | 功能基本成型，验证不足 |
| 摘要库与逻辑校验 | 已有 | 部分 | 已有 | 未完整独立暴露 | 部分 | 待补全 | 服务层较完整，前端/API 不足 |
| 原始文件解析 | 已有 | 已有 | 已有 | 缺少专用 API | 部分 | 待补全 | 服务层有能力，产品闭环不足 |
| 业务循环审计 | 已有 | 已有 | 已有 | 缺少 API | 未接入 | 待补全 | 模型/服务雏形，闭环不足 |
| 内控测试 | 已有 | 已有 | 已有 | 缺少 API | 未接入 | 待补全 | 服务层有能力，闭环不足 |
| 会计主体语义映射 | 已有 | 已有 | 已有 | 缺少 API | 未接入 | 待补全 | 代码与文档状态不一致 |
| 内部核算单位 | 已有 | 已有 | 已有 | 缺少 API | 未接入 | 待补全 | 数据底座较强，操作层不足 |
| 会计期间快照/结账 | 已有 | 已有 | 已有 | 已有 | 可由 API 支撑 | 已有 | 当前完成度最高 |
| 事务性设计 | 已有 | 已有 | 已有 | 缺少 API | 未接入 | 待补全 | 底层存在，运维/审计查询不足 |
| Agent 入口 | 已规划 | 无/少 | 无/少 | 缺少 | 缺少 | 无 | 仍属后续规划 |

## 关键风险与缺口

### 1. 文档状态与代码状态不完全一致

部分规范中任务显示完成，但 checklist 未完成；部分代码已有模型和服务，但规范任务仍未勾选。这会造成项目管理误判。

建议后续统一采用六级完成标准：

```text
文档完成 < 数据模型完成 < 服务完成 < API 完成 < 前端接入完成 < 测试与真实数据验证完成
```

### 2. 服务层多，API 层少

当前许多重要能力只在 service 层存在，前端和未来 Agent 无法稳定调用。尤其缺少：

- 审计测试 API。
- 原始文件解析 API。
- 业务循环 API。
- 内控测试 API。
- 会计主体 API。
- 内部核算单位 API。
- 物料/BOM API。
- 事务日志 API。
- Agent API。

### 3. 前端流程有 mock 数据

记账模式和审计模式页面已经搭建，但部分关键步骤仍是演示型逻辑。例如审计测试页面仍存在模拟发现数量的逻辑。对于财务系统来说，这会影响真实验证。

### 4. 运行环境状态需要重新确认

历史文档对 Qdrant、AI API、Embedding、本地服务状态有不同时间点的描述。下一步应重新做一次运行时验证，确认当前真实状态。

### 5. 权限与审计留痕仍需加强

结账、反结账、风险复核、审计测试、手动回滚等动作都属于高风险财务动作，后续需要补权限、操作者、原因、日志和追溯链路。

## Proposed Changes / 下一步建议动作

### 阶段 A：先统一真实进度状态

#### 目标

形成一个准确的“项目真实进度矩阵”，避免只看 tasks.md 或只看代码造成误判。

#### 建议动作

1. 新建或更新总进度文档。
2. 按模块统计：文档、模型、服务、API、前端、测试、真实数据验证。
3. 对所有 `.trae/specs/*/tasks.md` 和 `checklist.md` 做一次同步修正。

#### 涉及路径

- `.trae/specs/*/tasks.md`
- `.trae/specs/*/checklist.md`
- `.trae/documents/project-progress-status-plan.md`

### 阶段 B：运行环境重新验证

#### 目标

确认项目当前能否稳定运行，而不是仅依据历史文档判断。

#### 建议验证项

1. 后端测试。
2. 前端 typecheck/lint/build。
3. SQLite 当前数据库状态。
4. Qdrant 本地/远程状态。
5. AI API 配置状态。
6. Embedding 服务是否可用。
7. Docker/PostgreSQL/Redis 是否仍需启用。

#### 涉及路径

- `backend/pyproject.toml`
- `frontend/package.json`
- `backend/app/core/config.py`
- `backend/app/services/vector_store_service.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/ai_client_service.py`

### 阶段 C：优先补审计测试 API

#### 目标

让审计模式不再是演示流程，而是真实执行审计测试。

#### 建议新增文件

- `backend/app/api/routes_audit_tests.py`
- 如需要，可新增或调整 `backend/app/schemas/audit_test.py`

#### 建议接口

```text
POST /api/audit-tests/{job_id}/run
GET  /api/audit-tests/{job_id}/report
GET  /api/audit-tests/{job_id}/findings
```

#### 前端接入

重点替换：

- `frontend/src/pages/AuditMode/Step4RunTests.tsx`
- `frontend/src/pages/AuditMode/Step5ReviewFindings.tsx`

#### 为什么优先做

这是项目审计价值最高的闭环：原始资料 + 被审计单位分录 → 审计测试 → 审计发现。

### 阶段 D：补原始文件解析 API

#### 目标

把合同、发票、银行回单、入库单等原始证据从服务层能力变成可调用能力。

#### 建议新增文件

- `backend/app/api/routes_document_parsing.py`
- 如需要，可新增 `backend/app/schemas/document_parsing.py`

#### 建议接口

```text
POST /api/parse/contract
POST /api/parse/invoice
POST /api/parse/bank-statement
POST /api/parse/inventory-document
```

#### 涉及服务

- `backend/app/services/document_parsing_service.py`
- `backend/app/services/source_document_service.py`

### 阶段 E：补业务循环与内控 API

#### 目标

从单笔交易风险识别升级到流程风险识别。

#### 建议新增 API

业务循环：

```text
GET  /api/business-cycles
POST /api/business-cycles/build/{job_id}
POST /api/business-cycles/detect-breaks/{job_id}
GET  /api/business-cycles/{cycle_id}
```

内控测试：

```text
GET  /api/internal-controls
POST /api/internal-controls/test/{job_id}
GET  /api/internal-controls/alerts
```

#### 涉及服务

- `backend/app/services/business_cycle_service.py`
- `backend/app/services/internal_control_service.py`

### 阶段 F：补前端真实 API 接入，逐步去 mock

#### 优先页面

1. `frontend/src/pages/AuditMode/Step4RunTests.tsx`
2. `frontend/src/pages/AuditMode/Step5ReviewFindings.tsx`
3. `frontend/src/pages/AuditMode/Step3ImportEntries.tsx`
4. `frontend/src/pages/AccountingMode/Step3GenerateEntries.tsx`
5. `frontend/src/pages/AccountingMode/Step4ReviewEntries.tsx`

#### 前端 API 客户端

需要扩展：

- `frontend/src/api/client.ts`

### 阶段 G：补事务日志 API

#### 目标

让事务日志、失败回滚、手动回滚可以查询和审计。

#### 建议新增文件

- `backend/app/api/routes_transactions.py`

#### 建议接口

```text
GET  /api/transactions
GET  /api/transactions/{id}
POST /api/transactions/{id}/rollback
```

#### 涉及服务

- `backend/app/services/transaction_manager.py`

### 阶段 H：暂缓 Agent，等 API 工具体系稳定后再做

Agent 的价值是统一入口，但 Agent 需要稳定 API 作为工具。当前更建议先补 API 和前端真实接入，再做 Agent。

## Assumptions & Decisions

1. 当前项目目标仍以财务审计系统为主，而不是普通后台管理系统。
2. 短期以“真实审计闭环”为优先，不优先继续堆模型。
3. 现阶段货币计量只考虑人民币，不实现外币折算。
4. API 应按清晰业务动作拆分，便于权限、事务、日志、Agent 调用和测试。
5. Agent 入口后置，待审计测试、原始文件解析、业务循环、内控 API 稳定后再推进。
6. 前端 mock 去除要分步进行，优先审计模式，再记账模式。

## Verification Steps

后续执行建议按以下验证顺序：

### 1. 基础环境验证

```text
python -m pytest backend/tests
pnpm --dir frontend lint
```

如项目存在 build 命令，再运行：

```text
pnpm --dir frontend build
```

### 2. 后端 API 验证

每新增一个 API 模块，需要验证：

1. 路由已在 `backend/app/main.py` 注册。
2. OpenAPI 可识别路由。
3. 正常请求返回 200/201。
4. 错误请求返回合理 400/404。
5. 数据库写入符合预期。
6. 事务失败能回滚。

### 3. 前端接入验证

每替换一个 mock 页面，需要验证：

1. 页面加载不报错。
2. API 请求成功。
3. loading/error/empty 状态可显示。
4. 返回数据与页面字段一致。
5. TypeScript 检查通过。

### 4. 财务审计业务验证

建议用一组最小样例验证：

1. 一笔采购合同。
2. 一张入库单。
3. 一张发票。
4. 一笔付款银行流水。
5. 一张被审计单位凭证。

验证能否形成：

```text
原始资料 → 结构化证据 → 会计分录 → 审计测试 → 审计发现 → 复核记录
```

## Recommended Next Action

我建议下一步不要马上做 Agent，也不要继续扩展新概念。推荐动作是：

> 优先实现“审计测试 API + 前端审计模式 Step4/Step5 去 mock”。

理由：

1. 它最贴近审计软件核心价值。
2. 可以检验已有导入、分录、风险、原始资料解析是否真的能协同工作。
3. 做完后系统从“有很多服务”变成“能跑一条真实审计流程”。
4. 后续 Agent 才有稳定工具可调用。

建议最小任务包：

1. 新增 `backend/app/api/routes_audit_tests.py`。
2. 复用 `backend/app/services/audit_test_service.py`。
3. 在 `backend/app/main.py` 注册路由。
4. 扩展 `frontend/src/api/client.ts`。
5. 替换 `AuditMode/Step4RunTests.tsx` 的随机模拟逻辑。
6. 替换 `AuditMode/Step5ReviewFindings.tsx` 的 mock findings。
7. 增加后端 API 测试与前端 typecheck。
