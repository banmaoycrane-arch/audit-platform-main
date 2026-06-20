# 三大财务报表（Financial Statements）Spec

## Why

期初余额已上线，账具备"起点 + 本期发生 = 期末"的逻辑闭合条件。当前系统仍缺少「资产负债表 / 利润表 / 科目余额表」三大基础报表的生成与展示，导致核算成果无法以财务报告形式呈现，也无法为后续审计程序（账面金额 → 实质性测试）提供口径统一的数字。本 spec 在已有 [OpeningBalance](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/db/models.py)、[AccountingEntry](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/db/models.py)、[ChartOfAccounts](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/db/models.py)、[AccountingPeriod](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/db/models.py) 之上构建报表服务。

## What Changes

### A. 报表计算服务

- 新增 `financial_statements_service.py`：
  - `compute_account_balances(org_id, period_id)`：
    - 输入：组织、期间
    - 输出：每个一级科目的 `{opening_debit, opening_credit, period_debit, period_credit, closing_debit, closing_credit}`
    - 计算规则：
      - 期初借/贷 = `OpeningBalance` 中该科目记录
      - 本期借/贷 = `AccountingEntry` 中 `voucher_date ∈ [period_start, period_end]` 的合计
      - 期末借/贷：
        - 借方科目（`direction=debit`）：`closing_debit = max(opening_debit + period_debit - opening_credit - period_credit, 0)`，`closing_credit = max(opening_credit + period_credit - opening_debit - period_debit, 0)`
        - 贷方科目反之
  - `trial_balance_report(org_id, period_id)`：基于上面输出科目余额表（含期初/本期/期末借贷六列）
  - `balance_sheet(org_id, period_id)`：资产负债表
    - 资产 = 类别为 `asset` 的所有科目期末借方余额 - 期末贷方余额
    - 负债 = 类别为 `liability` 的所有科目期末贷方余额 - 期末借方余额
    - 权益 = 类别为 `equity` 期末贷方余额 - 期末借方余额
    - 校验等式：资产 = 负债 + 权益
  - `income_statement(org_id, period_id)`：利润表
    - 主营业务收入 / 其他业务收入 / 投资收益 / 营业外收入（profit 类，贷方为正）
    - 主营业务成本 / 其他业务成本 / 销售费用 / 管理费用 / 财务费用 / 资产减值损失 / 营业外支出 / 所得税费用（profit 类，借方为正）
    - 营业利润 = 收入 - 成本 - 期间费用
    - 利润总额 = 营业利润 + 营业外收入 - 营业外支出
    - 净利润 = 利润总额 - 所得税费用

### B. API

- `GET /api/reports/trial-balance?organization_id=&period_id=` 科目余额表
- `GET /api/reports/balance-sheet?organization_id=&period_id=` 资产负债表
- `GET /api/reports/income-statement?organization_id=&period_id=` 利润表

### C. 前端

- 新增 `Reports/TrialBalancePage.tsx`：表格 + 借贷合计 + 平衡校验
- 新增 `Reports/BalanceSheetPage.tsx`：资产、负债、权益分组 + 三大恒等式校验
- 新增 `Reports/IncomeStatementPage.tsx`：营业利润 / 利润总额 / 净利润分块展示
- 主导航 `MainShell.tsx` 增加「报表」一级 + 三个子项
- `App.tsx` 注册三个路由

## Impact

- 受影响 specs：
  - `opening-balances`：作为期初数据源
  - `accounting-period-snapshot`：报表生成可作为快照内容
  - `auto-generate-entries-from-source`：通过分录数据驱动本期发生
- 受影响代码：
  - 后端：`services/financial_statements_service.py`、`api/routes_reports.py`、`main.py`
  - 前端：`pages/Reports/*Page.tsx`、`api/client.ts`、`App.tsx`、`layout/MainShell.tsx`

## ADDED Requirements

### Requirement: 科目余额表

系统 SHALL 提供 `GET /api/reports/trial-balance`，按科目代码升序返回每个科目的期初/本期/期末借贷六列，并附借贷合计行。

#### Scenario: 成功生成科目余额表
- **WHEN** 用户传入 `organization_id` 与 `period_id`
- **THEN** 返回 `{ rows, totals: { opening_debit, opening_credit, period_debit, period_credit, closing_debit, closing_credit }, is_balanced }`

#### Scenario: 缺少期间返回 404
- **WHEN** `period_id` 不存在
- **THEN** 返回 404

### Requirement: 资产负债表

系统 SHALL 提供 `GET /api/reports/balance-sheet`，返回资产/负债/权益分组及恒等式校验。

#### Scenario: 平衡校验
- **WHEN** 调用接口
- **THEN** 响应中含 `assets_total`、`liabilities_total`、`equity_total`、`is_balanced = (assets_total == liabilities_total + equity_total)`

### Requirement: 利润表

系统 SHALL 提供 `GET /api/reports/income-statement`，返回收入、成本、期间费用、营业利润、利润总额、净利润等。

#### Scenario: 净利润计算
- **WHEN** 调用接口
- **THEN** 响应中 `net_profit = total_profit - income_tax`，且 `total_profit = operating_profit + non_operating_income - non_operating_expense`

### Requirement: 前端报表页面

系统 SHALL 提供 3 个报表页面：科目余额表、资产负债表、利润表，并由主导航「报表」入口进入。

#### Scenario: 期间切换刷新
- **WHEN** 用户切换期间
- **THEN** 表格重新拉取该期间报表

## MODIFIED Requirements

### Requirement: SAAS Shell 主导航
新增「报表」一级菜单（科目余额表 / 资产负债表 / 利润表）。

## REMOVED Requirements

无。
