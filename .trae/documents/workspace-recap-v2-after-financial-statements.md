# 工作区上下文复盘与下一阶段目标 Plan v2

> 生成时间：2026-06-17 financial-statements 完成后
> 仅作 **只读规划**，不执行任何代码改动；待用户批准后再进入实施阶段。
> 本文档是 [workspace-recap-and-next-step.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/workspace-recap-and-next-step.md) 的更新版，反映 financial-statements 完成后的状态。

---

## Phase 1 — 探索结果

### 1. spec 完成度全景（20 个 spec）

| Spec | tasks | checklist | 状态 |
|------|-------|-----------|------|
| accounting-period-snapshot | 7/7 | 20/20 | ✅ 完成 |
| audit-step3-real-entries | 4/4 | 8/8 | ✅ 完成 |
| basic-data-pages | 6/6 | 5/5 | ✅ 完成 |
| entry-line-number | 6/6 | 11/11 | ✅ 完成 |
| export-accounting-package | 3/3 | 9/9 | ✅ 完成 |
| **financial-statements** | **5/5** | **9/9** | **✅ 完成（最新）** |
| opening-balances | 6/6 | 12/12 | ✅ 完成 |
| persist-audit-findings | 6/6 | 10/10 | ✅ 完成 |
| saas-shell-and-navigation | 3/3 | 5/5 | ✅ 完成 |
| summarize-requirements | 7/7 | 19/19 | ✅ 完成 |
| auto-generate-entries-from-source | 9/9 (4/7 部分) | 13/15 | 🔵 主路径完成 |
| adaptive-import-engine | 7/7 | 25/30 | 🔵 5 项人工验证未关 |
| entity-semantic-mapping | 7/7 | 部分 | 🔵 后端齐备 |
| progress-review | 7/7 | 17/21 | 🔵 4 项受 Docker 限制 |
| business-cycle-audit | 4/6 | 0/19 | 🟡 缺 API（Task 5）+ 测试 |
| document-parsing-engine | 5/7 | 0/26 | 🟡 路由有，文档对齐欠缺 |
| internal-control-audit | 4/6 | 0/21 | 🟡 缺 API + 测试 |
| transactional-design | 3/6 | 0/18 | 🟡 缺状态管理 + API + 测试 |
| internal-accounting-unit | 3/11 | 7/31 | 🟡 数据底座有 |
| summary-library | 6/11 | 5/35 | 🟡 服务有，前端缺独立页 |

完成 / 部分完成 / 待启动 = 11 / 4 / 5

### 2. 已挂载 API（[main.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/main.py)）— 14 个路由

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

### 3. 前端页面（[frontend/src/pages](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages)）

```text
SAAS Shell + 嵌套路由：
  WorkspacePage / EntriesPageRoute / RisksPageRoute / RiskDetailPage
  AccountingPeriodsPage
  BasicData/{ChartOfAccounts, Counterparties, OpeningBalances}
  Reports/{TrialBalance, BalanceSheet, IncomeStatement}

向导路由（保留）：
  HomePage
  AccountingMode/Step1..Step5
  AuditMode/Step1..Step6
```

### 4. 测试与质量基线

```text
后端: 62 collected, pytest exit 0
前端: TypeScript lint 通过
```

### 5. 财务/审计闭环现状

```text
账闭合：基础资料 ── 期初余额 ── 本期分录 ── 三大报表
                                        ↓
                  仅差期末损益结转（balance_sheet 在有损益时不平衡）

审计闭环：原始资料 ─ 被审计单位分录 ─ 审计测试 ─ 审计发现 ─ 复核留痕
                                        ↓
                  缺：业务循环 API、内控测试 API、Step6 报告导出
```

### 6. 用户已提出但仍未独立立 spec 的需求

- 审计模式「**导入序时簿模式**」（用户原话，"导入审计证据缺乏导入序时簿模式"）
- 凭证管理 / 凭证字汇总（截图诉求）
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

## Phase 3 — 提案：下一阶段任务目标

### 阶段一：账闭合最后一公里（强烈推荐）

#### 🥇 A. 期末损益结转（period-close-pl-transfer）

##### Why（最关键）

[financial_statements_service.balance_sheet()](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/services/financial_statements_service.py) 当前在有损益发生时无法满足 `assets = liabilities + equity`。原因：损益类（6001 / 6401 / 6601 / 6801…）尚未结转到 4103 本年利润。这是当前账闭合**唯一未补**的环节。

##### What Changes

- 新增 `backend/app/services/period_close_service.py`
  - `auto_pl_transfer(org_id, period_id)`：
    - 收入类（贷方为正）：`借 6001 / 贷 4103`
    - 成本费用类（借方为正）：`借 4103 / 贷 6401/6601/...`
    - 写入 [accounting_entries](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/db/models.py#L261)，凭证字 `转-期末-{period_code}`
    - 标记 [AccountingPeriod.status](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/db/models.py#L298) = `pl_transferred`
  - `reverse_pl_transfer(org_id, period_id)`：反结转
- 新增 API：
  - `POST /api/accounting-periods/{id}/pl-transfer`
  - `POST /api/accounting-periods/{id}/pl-transfer/reverse`
- 前端：
  - [AccountingPeriodsPage](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/AccountingPeriodsPage.tsx) 增加「损益结转 / 反结转」按钮列
  - [BalanceSheetPage](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/Reports/BalanceSheetPage.tsx) 在不平衡时附"是否未结转损益？"提示，并提供跳转链接
- 测试：
  - 单测覆盖：结转后利润表净利润 = 4103 增加额；balance_sheet.is_balanced == true
  - 反结转：4103 与各损益科目恢复

##### 验收

```text
WHEN  执行 POST /api/accounting-periods/{id}/pl-transfer
THEN  对应期间产生若干结转分录，损益类期末为 0
AND   资产负债表恒等式成立（is_balanced=true）
AND   利润表净利润 == 本年利润累计
```

---

### 阶段二：审计闭环补齐

#### 🥈 B. 业务循环 API + 前端（business-cycle-audit Task 5/6）

服务层已实现，仅暴露 API + 在 [Step4RunTests](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/AuditMode/Step4RunTests.tsx) 添加循环检测面板。

#### 🥉 C. 内控测试 API + 前端（internal-control-audit Task 5/6）

服务层已实现，与 B 类似。

#### D. Step6 审计报告真实导出

复用 [routes_export.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/api/routes_export.py) 模式，把审计报告导出 docx / xlsx。

---

### 阶段三：信息架构与体验扩展（可后续排期）

| 顺序 | spec / 任务 | 价值 |
|------|------|------|
| 1 | dashboard-home（待立 spec） | 工作台 KPI + 财务曲线 |
| 2 | audit-day-book-import（待立 spec） | 审计模式导入序时簿 |
| 3 | inventory-ledger（待立 spec） | 库存账（FIFO/加权平均） |
| 4 | fixed-assets（待立 spec） | 资产卡片 + 折旧 |
| 5 | settlement-offset（待立 spec） | 应收应付对账 |
| 6 | funds-account-management（待立 spec） | 资金账户档案 |
| 7 | global-search-and-help（待立 spec） | 全局搜索 |
| 8 | summary-library 前端 | 摘要模板维护 UI |
| 9 | transactional-design Task 4-6 | 事务回滚 API |
| ⏸ | Agent 入口 | 暂不启动 |

---

## Phase 4 — 推荐路径

> **强烈建议从「A 期末损益结转」开始。**
>
> 1. 体量最小（一个 service + 两个 API + 两个按钮）
> 2. 解决最显眼的可信度问题（资产负债表不平衡）
> 3. 不依赖任何新 spec；纯粹补齐已有报表的"账闭合"
> 4. 完成后立即提升记账模式 + 报表两个工作流的可信度
>
> 之后串行：A → B（业务循环 API）→ C（内控 API）→ D（Step6 导出）

---

## Assumptions & Decisions（沿用历次决议）

- 货币锁定 CNY
- 默认科目库仅一级
- 二级辅助核算转 EntryTag（向量同步留 `vector_pending=true`）
- Agent 入口暂停
- 后端测试基线 pytest exit 0；前端 lint 通过

---

## Verification Steps（执行 A 时）

1. 后端单测：在 [test_reports_api.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/tests/test_reports_api.py) 之上新增结转用例
2. 后端全量：`python -m pytest backend/tests`
3. 前端：`pnpm --dir frontend lint`
4. 浏览器手测：[AccountingPeriodsPage](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/AccountingPeriodsPage.tsx) → [BalanceSheetPage](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/Reports/BalanceSheetPage.tsx) 恒等式 ❌→✅
5. 更新相关 spec 的 checklist 备注

---

## 编程常识 + 财务视角小结

- **编程**：报表服务"先按科目算期末，再按类别汇总"，因此结转动作只需向 [accounting_entries](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/db/models.py#L261) 写入新分录即天然影响下游报表
- **财务**：期末损益结转是月结的最后一步——"先结转、再出表、再结账"是中国会计准则下的标准动作
- **审计**：损益结转后才能正确执行 `资产 = 负债 + 所有者权益` 恒等式校验，这是审计程序中"重新计算"的基础

---

## 等待用户决策

请回复以下任一选项：

- **A**：立刻启动「期末损益结转 period-close-pl-transfer」（推荐）
- **B**：启动「业务循环 API + 前端」
- **C**：启动「内控测试 API + 前端」
- **D**：自定义其他目标（请在下一条消息说明）
