# Tasks

- [x] Task 1: 数据模型
  - [x] SubTask 1.1: 在 `backend/app/db/models.py` 新增 `OpeningBalance`，字段含 organization_id/period_id/account_code/debit_balance/credit_balance/currency/notes/timestamps
  - [x] SubTask 1.2: 添加唯一约束 `(organization_id, period_id, account_code)`

- [x] Task 2: 服务层
  - [x] SubTask 2.1: `opening_balance_service.py` 提供 list/upsert/bulk_upsert/delete_one/trial_balance

- [x] Task 3: API 路由
  - [x] SubTask 3.1: `routes_opening_balances.py` 暴露上述能力
  - [x] SubTask 3.2: 在 `main.py` 注册路由

- [x] Task 4: 前端类型与 client
  - [x] SubTask 4.1: `client.ts` 新增 `OpeningBalance`/`TrialBalance` 类型与 5 个方法

- [x] Task 5: 前端页面
  - [x] SubTask 5.1: `BasicData/OpeningBalancesPage.tsx` 实现期间选择 + 表格 + 行内编辑 + 试算平衡
  - [x] SubTask 5.2: 在 `App.tsx` 注册 `/basic/opening-balances`
  - [x] SubTask 5.3: 在 `MainShell.tsx` 主导航中增加入口

- [x] Task 6: 测试与验证
  - [x] SubTask 6.1: 后端测试覆盖：upsert / 唯一约束 / 试算平衡 / 删除（5 passed）
  - [x] SubTask 6.2: 前端 TypeScript lint 通过
  - [x] SubTask 6.3: 后端全量 pytest 通过（58 collected, exit 0）

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 4
- Task 6 depends on Task 1-5
