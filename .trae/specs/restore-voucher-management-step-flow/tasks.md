# Tasks

- [x] Task 1: 恢复财务总账下的凭证管理多 Step 菜单
  - [x] SubTask 1.1: 修改 `MainShell.tsx`，将“财务总账 / 凭证管理”改为父菜单
  - [x] SubTask 1.2: 凭证管理下增加 Step 1-5 子菜单
  - [x] SubTask 1.3: 凭证管理下保留“凭证列表”入口 `/ledger/entries`
  - [x] SubTask 1.4: 当前路径在 `/ledger/vouchers/step/*` 或 `/accounting/step/*` 时正确高亮

- [x] Task 2: 增加财务总账语义路由
  - [x] SubTask 2.1: 修改 `App.tsx`，增加 `/ledger/vouchers/step/1` 到 `/ledger/vouchers/step/5`
  - [x] SubTask 2.2: 复用现有 `AccountingMode` Step1-5 页面组件
  - [x] SubTask 2.3: 保留 `/accounting/step/1` 到 `/accounting/step/5` 兼容旧路径

- [x] Task 3: 修正凭证流程页跳转路径
  - [x] SubTask 3.1: 让 `FlowNav` 或页面跳转逻辑支持当前路径前缀
  - [x] SubTask 3.2: 当用户从 `/ledger/vouchers/step/*` 进入流程时，上一步/下一步仍留在 `/ledger/vouchers/step/*`
  - [x] SubTask 3.3: 保留 `jobId`、`periodId` 等 query 参数

- [x] Task 4: 更新工作台入口说明
  - [x] SubTask 4.1: 修改 `WorkspacePage.tsx`，财务总账入口优先进入 `/ledger/vouchers/step/1`
  - [x] SubTask 4.2: 说明凭证管理是多步骤流程，不是单页分录列表

- [x] Task 5: 验证
  - [x] SubTask 5.1: 运行前端 `npm run lint`
  - [x] SubTask 5.2: 验证 `/ledger/vouchers/step/1` 可访问
  - [x] SubTask 5.3: 验证 `/ledger/vouchers/step/5` 可访问
  - [x] SubTask 5.4: 验证 `/accounting/step/1` 旧路径仍可访问
  - [x] SubTask 5.5: 验证 `/ledger/entries` 凭证列表仍可访问

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 can run in parallel with Task 1-3
- Task 5 depends on Task 1-4
