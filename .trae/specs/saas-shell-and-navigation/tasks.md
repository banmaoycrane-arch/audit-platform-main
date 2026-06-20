# Tasks

- [x] Task 1: 新增 Shell 组件
  - [x] SubTask 1.1: `MainShell.tsx`（Layout，含 Header/Sider/Content）
  - [x] SubTask 1.2: 主导航（工作台、凭证、基础资料、期间、风险、记账模式、审计模式）
  - [x] SubTask 1.3: TopBar 集成在 MainShell 内（标题 + 搜索 + 账套）

- [x] Task 2: 路由嵌套
  - [x] SubTask 2.1: 修改 `App.tsx`，将 `/workspace` `/entries` `/risks` `/periods` `/basic/coa` `/basic/counterparties` 放进 `MainShell`
  - [x] SubTask 2.2: 保留 `/`、`/accounting/*`、`/audit/*` 路由可访问

- [x] Task 3: 验证
  - [x] SubTask 3.1: 前端 lint 通过
  - [x] SubTask 3.2: EntriesPageRoute/RisksPageRoute 让原 props 驱动页面接入嵌套路由

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
