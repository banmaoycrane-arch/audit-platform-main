# 工作区需求复盘与下一步目标 Plan

> 截至 2026-06-17 的工作区上下文复盘。
> 本文档仅作 **只读规划**，不执行任何代码改动；待用户批准后再进入实施阶段。

---

## Phase 1 — 探索结果

### 1. spec 目录全景（20 个 spec）

| Spec | tasks | checklist | 完成度 |
|------|-------|-----------|--------|
| accounting-period-snapshot | 7/7 | 20/20 | ✅ 已完成 |
| audit-step3-real-entries | 4/4 | 8/8 | ✅ 已完成 |
| auto-generate-entries-from-source | 9/9（4 与 7 部分） | 13/15 | 🔵 主路径完成（向量同步、基础资料 UI 已交给其他 spec） |
| basic-data-pages | 6/6 | 5/5 | ✅ 已完成 |
| entry-line-number | 6/6 | 11/11 | ✅ 已完成 |
| export-accounting-package | 3/3 | 9/9 | ✅ 已完成 |
| financial-statements | 5/5 | 9/9 | ✅ 已完成（最新） |
| opening-balances | 6/6 | 12/12 | ✅ 已完成 |
| persist-audit-findings | 6/6 | 10/10 | ✅ 已完成 |
| saas-shell-and-navigation | 3/3 | 5/5 | ✅ 已完成 |
| summarize-requirements | 7/7 | 19/19 | ✅ 已完成 |
| adaptive-import-engine | 7/7 | 25/30 | 🔵 5 项人工验证未关 |
| entity-semantic-mapping | 7/7 | 部分 | 🔵 后端 + 部分前端 |
| progress-review | 7/7 | 17/21 | 🔵 4 项受 Docker 限制 |
| business-cycle-audit | 4/6 | 0/19 | 🟡 缺 API（Task 5）+ 测试 |
| document-parsing-engine | 5/7 | 0/26 | 🟡 路由有，文档对齐欠缺 |
| internal-control-audit | 4/6 | 0/21 | 🟡 缺 API + 测试 |
| transactional-design | 3/6 | 0/18 | 🟡 缺状态管理 + API + 测试 |
| internal-accounting-unit | 3/11 | 7/31 | 🟡 数据底座有 |
| summary-library | 6/11 | 5/35 | 🟡 服务有，前端缺独立页 |

### 2. 已挂载 API（[main.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/main.py)）

```text
/api/accounting-periods
/api/audit-tests              (含 findings 持久化 + review)
/api/coa
/api/counterparties
/api/document-parsing         (合同/发票/银行流水/入库)
/api/entities
/api/entries
/api/entry-generation         (草稿/落库)
/api/export                   (xlsx/csv/json)
/api/files
/api/import-jobs
/api/opening-balances
/api/reports                  (科目余额表/资产负债表/利润表)
/api/risks
```

### 3. 前端真实页面（[frontend/src/pages](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages)）

```text
HomePage / DashboardPage / WorkspacePage
AccountingMode/Step1..Step5
AuditMode/Step1..Step6
BasicData/{ChartOfAccounts, Counterparties, OpeningBalances}
Reports/{TrialBalance, BalanceSheet, IncomeStatement}
EntriesPage(Route) / RisksPage(Route) / RiskDetailPage / ImportPage / AccountingPeriodsPage
```

### 4. 最近测试基线

```text
后端: 62 collected, pytest exit 0
前端: TypeScript lint 通过
```

### 5. 财务/审计闭环现状

```text
基础资料  ── 期初余额  ── 本期分录  ── 三大报表
ChartOfAccounts × OpeningBalance × AccountingEntry × Reports
                                    ↓
                  会计循环已基本贯通（差期末损益结转）
审计闭环：
原始资料 → 被审计单位分录 → 审计测试 → 审计发现持久化 → 复核留痕
                                    ↓
                           已基本贯通（差导出 + 业务循环 + 内控）
```

### 6. 用户曾提及但仍未独立立 spec 的需求

- 审计模式「**导入序时簿模式**」（用户原话："导入审计证据缺乏导入序时簿模式"）
- 凭证管理 / 凭证字汇总（截图所示，目前只在 Step3 草稿表中展示）
- 资金账户档案（CoA 1002 与"资金账户"语义需要拆分）
- 库存账核算（入库/出库/库龄/结存价）
- 资产卡片 + 折旧 + 折旧凭证
- 期末损益结转（resolve 资产负债表恒等式不平衡）
- 全局搜索 / 帮助系统
- Dashboard 仪表盘（KPI + 财务曲线）
- 结算抵销（应收应付对账）
- 审计报告 Step6 真实导出
- 关键词摘要库前端（summary-library 的 UI 部分）

---

## Phase 2 — 需要澄清

> 不需要追问，已有充足信息。多个候选目标按优先级提供，由用户选择。

---

## Phase 3 — 提案：下一步执行目标

### 候选 P0（建议立即启动二选一）

#### 候选 A：🥇 期末损益结转（period-close-pl-transfer）

##### Why

当前 [financial_statements_service.balance_sheet()](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/services/financial_statements_service.py) 在本期有收入或费用时，资产负债表恒等式 `assets = liabilities + equity` 不会成立——因为损益类科目（6001/6401/6601/6801…）尚未结转到 4103「本年利润」。这是当前账闭合的最后一公里。

##### What Changes

- 新增服务：`period_close_service.py`
  - `auto_pl_transfer(org_id, period_id)`：自动按规则把本期所有 `category=profit` 科目余额转入 `4103 本年利润`
  - 借方损益类：`借 4103 本年利润 / 贷 6X01 (各成本/费用)`
  - 贷方损益类：`借 6X01 (各收入) / 贷 4103 本年利润`
  - 生成系统凭证字 `转-期末-{period_code}`
  - 写入 [accounting_entries](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/db/models.py#L261)
  - 标记当前期间为「已结转损益」（`AccountingPeriod.status = 'pl_transferred'`）
- API：`POST /api/accounting-periods/{id}/pl-transfer`
- 前端：在 [AccountingPeriodsPage](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/AccountingPeriodsPage.tsx) 加「损益结转」按钮，结转后跳转到资产负债表查看恒等式平衡

##### 验收

- 结转后 `balance_sheet.is_balanced = true`
- `audit_log` 记录系统凭证
- 已结转期间不可重复结转，但可反结转

---

#### 候选 B：🥇 业务循环 API + 前端（business-cycle-audit Task 5/6）

##### Why

`business-cycle-audit` 的 Task 1-4 已实现服务层（合同→入库→发票→付款关联、断裂检测、风险延伸），但 Task 5（API）和 Task 6（测试）未做，能力闲置。把循环检测能力暴露为 API 后，可在审计模式 Step4 中作为新增审计程序运行。

##### What Changes

- API：
  - `GET /api/business-cycles?import_job_id=` 返回该 job 的所有循环
  - `POST /api/business-cycles/detect-breaks` 触发断裂检测
  - `GET /api/business-cycles/risk-analysis?import_job_id=`
- 前端：在审计模式 Step4 增加「业务循环检测」面板
- 测试：覆盖关联、断裂、风险三类场景

---

### 候选 P1（按依赖排序）

| 顺序 | spec | 价值 |
|------|------|------|
| 1 | internal-control-audit Task 5/6 | 内控测试 API + 前端 |
| 2 | transactional-design Task 4/5/6 | 事务回滚状态管理 API |
| 3 | audit-day-book-import（待立 spec） | 审计模式导入序时簿 |
| 4 | inventory-ledger（待立 spec） | 库存账（FIFO/加权平均） |
| 5 | fixed-assets（待立 spec） | 资产卡片 + 折旧 |
| 6 | dashboard-home（待立 spec） | KPI + 财务曲线 |
| 7 | settlement-offset（待立 spec） | 应收应付对账 |
| 8 | global-search-and-help（待立 spec） | 全局搜索 |
| 9 | summary-library 前端 | 摘要模板维护 UI |
| 10 | audit-report-export Step6 | 审计报告真实导出 |
| ⏸ | Agent 入口（暂停） | 暂不启动 |

---

## Phase 4 — 推荐路径

> **强烈建议从「候选 A：期末损益结转」开始。**
>
> 理由：
> 1. 体量最小（一个 service + 一个 API + 一个按钮）
> 2. 解决最显眼的体感问题（资产负债表不平衡）
> 3. 不依赖任何新需求；纯粹补齐已有报表的"账闭合"
> 4. 完成后立刻提升前端可信度
>
> 之后再启动「候选 B：业务循环 API」推进审计闭环。

---

## Assumptions & Decisions

- 货币锁定 CNY（沿用 [adaptive-import-engine](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/adaptive-import-engine) 决策）
- 默认科目库仅一级（沿用 [auto-generate-entries-from-source](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/auto-generate-entries-from-source) 决策）
- 二级辅助核算转 EntryTag（向量同步留 `vector_pending=true`，待后续 spec 接入 Qdrant）
- Agent 入口仍暂停（沿用历次决议）

---

## Verification Steps（执行候选 A 时）

1. 后端单测：在已有 [test_reports_api.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/tests/test_reports_api.py) 之上新增结转用例，断言结转后 `balance_sheet.is_balanced == True`
2. 后端全量 `python -m pytest backend/tests`
3. 前端 `pnpm --dir frontend lint`
4. 浏览器手测：
   - 在 [AccountingPeriodsPage](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/AccountingPeriodsPage.tsx) 点击"结转损益"
   - 进入 [BalanceSheetPage](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/Reports/BalanceSheetPage.tsx) 查看恒等式 Banner 由 ❌ 变 ✅
5. 更新 `accounting-period-snapshot` 与 `financial-statements` 的 checklist 中关于"恒等式平衡"的备注

---

## 编程常识 + 财务视角小结

- **编程**：报表服务遵循"先按科目算期末，再按类别汇总"的两步走，因此结转动作只需向 [accounting_entries](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/db/models.py#L261) 写入新分录即可天然影响下游报表，无需修改报表服务
- **财务**：期末损益结转是月结的最后一步，"先结转、再出表、再结账"是中国会计准则下的标准动作
- **审计**：损益结转后才能正确执行 `assets = liabilities + equity` 恒等式校验，这是审计程序中的"重新计算"基础

---

## 等待用户决策

请确认下一步选择：
- **A**：立刻启动「期末损益结转」（推荐）
- **B**：启动「业务循环 API + 前端」
- **C**：自定义其他目标（在下一条消息中说明）
