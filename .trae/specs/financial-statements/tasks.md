# Tasks

- [x] Task 1: 报表计算服务
  - [x] SubTask 1.1: `financial_statements_service.py` 实现 `compute_account_balances`
  - [x] SubTask 1.2: `trial_balance_report`
  - [x] SubTask 1.3: `balance_sheet`
  - [x] SubTask 1.4: `income_statement`

- [x] Task 2: API 路由
  - [x] SubTask 2.1: `routes_reports.py` 暴露三个 GET 接口
  - [x] SubTask 2.2: `main.py` 注册路由

- [x] Task 3: 前端 client 与类型
  - [x] SubTask 3.1: `client.ts` 增加 `getTrialBalanceReport / getBalanceSheet / getIncomeStatement` 与对应类型

- [x] Task 4: 前端页面
  - [x] SubTask 4.1: `Reports/TrialBalancePage.tsx`
  - [x] SubTask 4.2: `Reports/BalanceSheetPage.tsx`
  - [x] SubTask 4.3: `Reports/IncomeStatementPage.tsx`
  - [x] SubTask 4.4: `App.tsx` 注册 `/reports/trial-balance`、`/reports/balance-sheet`、`/reports/income-statement`
  - [x] SubTask 4.5: `MainShell.tsx` 主导航增加「报表」一级 + 三个子项

- [x] Task 5: 测试与验证
  - [x] SubTask 5.1: 后端测试覆盖：科目余额表平衡、资产负债表恒等式、利润表计算（4 passed）
  - [x] SubTask 5.2: 前端 TypeScript lint 通过
  - [x] SubTask 5.3: 后端全量 pytest 通过（62 collected, exit 0）

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 1-4
