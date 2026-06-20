# 下一阶段执行路线图 II（D + A + C）Spec

## Why

用户在路线图 I 完成后选择 D / A / C 三项继续推进：
- **D** transactional-design Task 4-6：事务状态服务 + API + 测试
- **A** auto-generate-entries-from-source Task 7：基础资料前端页（CoA / Counterparty）
- **C** document-parsing-engine Task 6-7：文档解析 API + 测试

## What Changes（盘点 + 计划）

### 队列 D：transactional-design（需要真正实施）
- [transaction_manager.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/services/transaction_manager.py) 已存在（含 begin/commit/rollback/checkpoint 全套方法）
- **缺**：HTTP 暴露 + 测试覆盖
- 实施：
  - 新增 `backend/app/api/routes_transactions.py`：`GET /api/transactions`（列表+按 context 过滤）、`GET /{id}`、`POST /{id}/rollback`、`GET /{id}/operations`、`GET /summary`
  - 注册到 main.py
  - 新增 `backend/tests/test_transactions_api.py` ≥ 5 用例

### 队列 A：基础资料前端页（实际已实现，需补勾选）
- [ChartOfAccountsPage.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/BasicData/ChartOfAccountsPage.tsx) ✅ 存在并已注册路由 `/basic/coa`
- [CounterpartiesPage.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/BasicData/CounterpartiesPage.tsx) ✅ 存在并已注册路由 `/basic/counterparties`
- [MainShell.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/layout/MainShell.tsx) ✅ 已含「基础资料」侧边栏菜单
- 实施：仅同步勾选 [auto-generate-entries-from-source/tasks.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/auto-generate-entries-from-source/tasks.md) Task 7 的三个 SubTask

### 队列 C：document-parsing-engine（实际已实现，需补勾选）
- [routes_document_parsing.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/api/routes_document_parsing.py) ✅ 4 个端点（合同/发票/银行回单/出入库）
- [test_document_parsing_api.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/tests/test_document_parsing_api.py) ✅ 5 个测试，全量 88 passed 中已包含
- 实施：仅同步勾选 [document-parsing-engine/tasks.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/document-parsing-engine/tasks.md) Task 6 + Task 7

## Impact

- 后端：新增 routes_transactions.py + main.py 注册 + test_transactions_api.py
- spec 文档：3 份 tasks.md / checklist.md 同步勾选
- 前端：无需改动

## ADDED Requirements

### Requirement: 事务管理 API
系统 SHALL 提供事务查询、详情、操作列表、手动回滚、汇总统计 API，复用 [TransactionManager](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/services/transaction_manager.py) service。

#### Scenario: 查询事务详情
- **WHEN** `GET /api/transactions/{id}`
- **THEN** 200 + 含 status / operation_count / succeeded_count / failed_count

#### Scenario: 手动回滚 pending 事务
- **WHEN** `POST /api/transactions/{id}/rollback` 且事务状态为 pending
- **THEN** 200 + status 变为 rolled_back

#### Scenario: 已提交事务不可回滚
- **WHEN** 事务已 committed
- **THEN** 400

## MODIFIED Requirements
无。

## REMOVED Requirements
无。

## 财务视角说明

- **事务管理 API 的会计意义**：相当于 ERP 系统的「制单回滚」按钮——把"半生不熟"的批量操作（导入了一半就出错）一键撤销，确保账面只保留"完整闭合"的凭证。`pending → committed | rolled_back` 三态机正是 ACID 中的 Atomicity（原子性）。
- **基础资料页面的会计意义**：会计科目和往来单位是所有账务核算的"地基"——会计科目决定借贷分类（资产/负债/损益），往来单位决定应收应付的核算对象。这两个页面是日常使用频率最高的入口。
- **文档解析 API 的会计意义**：把扫描件 / Excel / 银行回单 → 结构化数据，是现代审计师"获取审计证据"环节的电子化升级，本系统已落地合同（含收入准则五步法）、发票、银行回单、出入库单四类。
