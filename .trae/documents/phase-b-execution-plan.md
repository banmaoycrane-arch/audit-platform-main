# Phase B 执行计划：审计业务流程 MVP

> 版本：v0.1  
> 日期：2026-06-23  
> 分支：`cursor/phase-b-audit-workflow-mvp-5d1b`  
> 前置：Phase A 已合入 `main`（PR #8）— 台账 `ledger_id` 持久化 + 模块查询 API  
> 规划母文档：`register-audit-workflow-plan.md` §8 Phase B  
> 验收级别：**L2** — 资金 / 往来 / 采购三角勾稽可跑出差异清单

---

## 1. 目标（一句话）

在 Phase A「能按账簿看台账」的基础上，让审计人员能**跑三条核心审计程序并看到差异清单**，不自动改账、结论需人工确认。

```text
银行调节表草稿     bank_cash_flow  ↔  GL 1001/1002
往来函证控制表     counterparty_ledger  ↔  Confirmation
采购三单匹配       contract  ↔  inventory  ↔  invoice
```

---

## 2. 现状盘点（main @ Phase A 后）

| 能力 | 已有 | 缺口（Phase B 要补） |
|------|------|----------------------|
| **银行** | `BankAccount` / `BankTransaction`；`auto_reconcile` 按金额+日期匹配 `AccountingEntry`（1002）；`BankReconciliationPage` | 无正式**调节表实体**；未达账项未结构化；银行日记账余额 vs 科目余额 vs 对账单余额三线未汇总 |
| **往来** | `counterparty_ledger` 视图（发票聚合余额）；`Counterparty` 主档 | 无 `Confirmation` 实体；无函证发起/回函/差异登记 |
| **采购** | `Contract` / `Invoice` / `InventoryDocument` 均有 `ledger_id`、`related_contract_id`、`related_invoice_id` | 无三单匹配引擎；无差异类型与清单 API |
| **底稿** | AI 导入 + 语义分解 + 归档路径 | 函证回函、调节表底稿挂接留 Phase C |

**复用原则**：在 `bank_service.auto_reconcile` 与 `module_register_service` 上扩展，不重复造轮子。

---

## 3. 子任务拆分（建议 3 个 PR / 里程碑）

### B1 — 银行调节表草稿（优先）

**用户故事**：审计员选定银行账户与截止日，系统生成调节表草稿：银行对账单余额、企业账面余额、已匹配项、未达账项、调节后余额是否一致。

| 项 | 内容 |
|----|------|
| **数据模型** | `BankReconciliation`（header：ledger_id, bank_account_id, period_end, statement_balance, book_balance, adjusted_balance, status=draft）<br>`BankReconciliationItem`（type: outstanding_deposit / outstanding_payment / book_only / bank_only, amount, ref_txn_id, ref_entry_id, note） |
| **服务** | `bank_reconciliation_service.py`：`build_draft()` 调用现有 `auto_reconcile` + 汇总未匹配流水与未匹配分录；`get_statement_balance()` 从 `BankStatement` 或账户 `current_balance` |
| **API** | `POST /api/bank/reconciliations` 创建草稿<br>`GET /api/bank/reconciliations/{id}` 详情<br>`GET /api/bank/reconciliations?ledger_id=` 列表 |
| **前端** | 扩展 `BankReconciliationPage`：「生成调节表」按钮 + 调节表预览（未达账项表格） |
| **测试** | `test_bank_reconciliation_draft.py`：种子数据 → 草稿 → 断言调节后余额公式 |
| **验收** | 调节表展示：银行余额 + 加：企业已收银行未收 − 减：企业已付银行未付 = 调节后余额；与账面余额差异可解释 |

**不做（留 Phase D）**：函证状态机、自动过账、多币种。

---

### B2 — 往来函证控制表

**用户故事**：从 `counterparty_ledger` 余额视图勾选往来单位，生成函证控制表行：账面余额、发函金额、回函金额、差异、状态。

| 项 | 内容 |
|----|------|
| **数据模型** | `CounterpartyConfirmation`（ledger_id, counterparty_id, balance_type, book_balance, confirmation_amount, reply_amount, difference, status: draft/sent/replied/exception, sent_at, replied_at, source_file_id 可空） |
| **服务** | `confirmation_service.py`：`create_from_balances(ledger_id, counterparty_ids?)` 从 `list_counterparty_balances` 批量生成；`record_reply()` 登记回函 |
| **API** | `POST /api/confirmations/generate`<br>`GET /api/confirmations?ledger_id=`<br>`PATCH /api/confirmations/{id}` 更新状态/回函金额 |
| **前端** | 新页 `/audit/confirmations` 或在往来台账页增加「生成函证」入口；控制表列表 + 差异 Tag |
| **测试** | `test_confirmation_api.py`：余额视图 → 生成 → 回函 → 差异计算 |
| **验收** | 至少支持应收/应付两类；差异 ≠ 0 时标红；不自动调整账面 |

**待决策（本阶段默认）**：函证复用 `Counterparty` 主档，独立 `CounterpartyConfirmation` 表（见母文档 §10 项 2）。

---

### B3 — 采购三单匹配

**用户故事**：对采购循环，按 `related_contract_id` 链起合同、入库单、发票，输出匹配状态与金额/数量差异清单。

| 项 | 内容 |
|----|------|
| **服务** | `three_way_match_service.py`：`match_purchase_cycle(ledger_id, contract_id?)` 返回 `{contract, inventory_docs[], invoices[], checks[], exceptions[]}` |
| **匹配规则（MVP）** | 同一 `related_contract_id`；金额容差 0.01；数量容差可选；缺单标记 `missing_inventory` / `missing_invoice` / `amount_mismatch` |
| **API** | `GET /api/audit/purchase-match?ledger_id=&contract_id=` 单合同<br>`GET /api/audit/purchase-match/summary?ledger_id=` 全账簿异常汇总 |
| **前端** | 采购台账或 `/inventory/purchase-in` 增加「三单匹配」抽屉/页；差异清单表 |
| **测试** | `test_three_way_match.py`：完整三单 / 缺发票 / 金额不一致 三场景 |
| **验收** | 可导出差异清单 JSON；差异是审计发现，不触发自动冲销 |

---

## 4. 推荐实施顺序与依赖

```text
B1 银行调节表 ──┐
                ├──▶ 均依赖 Phase A ledger_id + 模块查询
B2 往来函证 ────┤
                │
B3 三单匹配 ────┘（依赖 Contract/Invoice/Inventory 外键链，Phase A 已具备）
```

| 顺序 | 里程碑 | 理由 |
|------|--------|------|
| 1 | **B1** | PR #5 已有银行对账雏形，扩展成本最低，快速达到 L2 一条腿 |
| 2 | **B2** | 往来是审计高频程序；与 `counterparty_ledger` 视图直接衔接 |
| 3 | **B3** | 采购循环勾稽；外键已就绪，纯逻辑 + 展示 |

每个里程碑：**后端服务 + API + 测试 → 最小前端 → 单独 PR 合入 main**，降低 review 风险。

---

## 5. 技术约定

- 所有查询必须带 `ledger_id`（与 Phase A 一致）
- 新表 Alembic 迁移：`0008_bank_reconciliation.py`、`0009_counterparty_confirmation.py`（B3 可无新表）
- SQLite 开发：`main.py` `_ensure_local_sqlite_schema` 同步补列（与 Phase A 模式一致）
- 人工复核：所有「确认结论」仅更新业务状态，**不写** `AccountingEntry`
- 前端：Ant Design Table + Tag；新 API 进 `frontend/src/api/client.ts`

---

## 6. 验收清单（L2）

| # | 场景 | 通过标准 |
|---|------|----------|
| L2-1 | 银行调节 | 选定账户生成草稿，未达账项与账面差异可逐项对应 |
| L2-2 | 往来函证 | 从余额视图生成控制表，回函后差异可计算 |
| L2-3 | 三单匹配 | 采购合同下三单齐全则 matched；缺单或金额差则进 exceptions |
| L2-4 | 账簿隔离 | 账簿 A 的程序/清单不出现在账簿 B |
| L2-5 | 构建 | `pytest` 新增用例全绿；`pnpm build:frontend` 通过 |

---

## 7. 首周起步（B1 具体任务）

开发者在 `cursor/phase-b-audit-workflow-mvp-5d1b` 上按下列 checklist 开工：

- [x] `0008` 迁移 + `BankReconciliation` / `BankReconciliationItem` 模型
- [x] `bank_reconciliation_service.build_draft()`
- [x] `routes_bank.py` 增加 reconciliation 端点
- [x] `test_bank_reconciliation_draft.py`
- [x] `BankReconciliationPage` 调节表预览 UI
- [ ] 文档：本文件 B1 项勾选 + PR 描述链回 L2-1

**首 PR 标题建议**：`feat(phase-b): 银行调节表草稿（B1）`

---

## 8. 与后续 Phase 的关系

| Phase | 关系 |
|-------|------|
| **Phase C** | 函证回函 PDF、调节表定稿挂 `WorkpaperVersion` |
| **Phase D** | 审计程序状态机（draft → sent → replied → concluded）编排 B2/B1 |

---

## 附录：关键文件索引

| 用途 | 路径 |
|------|------|
| 银行对账（现有） | `backend/app/services/bank_service.py` |
| 银行 API | `backend/app/api/routes_bank.py` |
| 往来余额视图 | `backend/app/services/module_register_service.py` |
| 银行前端 | `frontend/src/pages/Bank/BankReconciliationPage.tsx` |
| 模块台账页 | `frontend/src/pages/ModuleRegisterPage.tsx` |
| 边界规划 | `.trae/documents/register-audit-workflow-plan.md` |
