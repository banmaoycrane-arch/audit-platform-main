# Tasks

- [x] Task 1: 统一路由 Shell
  - [x] SubTask 1.1: 修改 `frontend/src/App.tsx`，将 `/accounting/step/*` 与 `/audit/step/*` 放入 `MainShell`
  - [x] SubTask 1.2: 保留 `/accounting`、`/audit` 默认重定向
  - [x] SubTask 1.3: 确认原有直接 URL 仍可访问

- [x] Task 2: 优化侧边栏菜单
  - [x] SubTask 2.1: 修改 `frontend/src/layout/MainShell.tsx`，新增记账模式 Step 1-5 子菜单
  - [x] SubTask 2.2: 新增审计模式 Step 1-6 子菜单
  - [x] SubTask 2.3: 修复 selectedKey/openKeys，让当前步骤正确高亮
  - [x] SubTask 2.4: 保留基础资料、期间、报表、风险、Agent 菜单

- [x] Task 3: 增强页面内流程导航
  - [x] SubTask 3.1: 为记账步骤页补充“返回工作台 / 上一步 / 下一步”导航一致性
  - [x] SubTask 3.2: 为审计步骤页补充“返回工作台 / 上一步 / 下一步”导航一致性
  - [x] SubTask 3.3: 跳转时保留已有 `jobId`、`periodId` 等 query 参数

- [x] Task 4: 工作台入口卡片
  - [x] SubTask 4.1: 修改 `frontend/src/pages/WorkspacePage.tsx`，增加常用测试入口卡片
  - [x] SubTask 4.2: 入口包括：记账流程、审计流程、基础资料、会计期间、报表、Agent 助手

- [x] Task 5: 验证
  - [x] SubTask 5.1: 运行 `npm run lint`
  - [x] SubTask 5.2: 验证关键 URL 可访问：`/workspace`、`/accounting/step/1`、`/accounting/step/5`、`/audit/step/1`、`/audit/step/6`、`/agent`

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 can run in parallel with Task 2/3
- Task 5 depends on Task 1-4
