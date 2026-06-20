# Tasks

- [x] Task 1: 后端用户模型扩展团队关联
  - [x] SubTask 1.1: 修改 `backend/app/models/user.py`，增加 `team_id` 字段（Integer, nullable）
  - [x] SubTask 1.2: 新增 `backend/app/models/team.py` — Team 模型（id, name, type, created_at）
  - [x] SubTask 1.3: 在 `models/__init__.py` 导入 Team
  - [x] SubTask 1.4: 数据库自动建表（SQLite 兼容）

- [x] Task 2: 后端团队级 Dashboard API
  - [x] SubTask 2.1: 修改 `backend/app/api/routes_dashboard.py`，扩展 `GET /api/dashboard/summary` 返回团队级数据
  - [x] SubTask 2.2: 数据包含：凭证待处理数、未结账期间数、未审计期间数、风险数量、通知数量
  - [x] SubTask 2.3: 从 `current_user` 获取 `team_id`，过滤数据

- [x] Task 3: 前端首页重写为团队业务大盘
  - [x] SubTask 3.1: 重写 `frontend/src/pages/WorkspacePage.tsx` 为团队大盘
  - [x] SubTask 3.2: 顶部展示：用户名称、团队名称、消息通知图标
  - [x] SubTask 3.3: 模块状态卡片区：财务总账、审计系统、银行模块、税务模块、基础资料
  - [x] SubTask 3.4: 每个卡片显示关键指标和快捷入口
  - [x] SubTask 3.5: 工作进度提醒区（如：本月还有 2 个期间未结账）

- [x] Task 4: 前端模块专属工作台
  - [x] SubTask 4.1: 新增 `frontend/src/pages/Workspaces/LedgerWorkspace.tsx` — 财务总账工作台
  - [x] SubTask 4.2: 新增 `frontend/src/pages/Workspaces/AuditWorkspace.tsx` — 审计工作台
  - [x] SubTask 4.3: 新增 `frontend/src/pages/Workspaces/BankWorkspace.tsx` — 银行工作台（占位）
  - [x] SubTask 4.4: 新增 `frontend/src/pages/Workspaces/TaxWorkspace.tsx` — 税务工作台（占位）
  - [x] SubTask 4.5: 新增 `frontend/src/pages/Workspaces/BasicDataWorkspace.tsx` — 基础资料工作台（占位）
  - [x] SubTask 4.6: 每个工作台有专属布局：左侧功能列表 + 右侧数据卡片/图表/导航条

- [x] Task 5: 左侧导航与模块工作台联动
  - [x] SubTask 5.1: 修改 `frontend/src/layout/MainShell.tsx`
  - [x] SubTask 5.2: 每个一级模块下增加“工作台”子菜单，指向 `/ledger/workspace`、`/audit/workspace` 等
  - [x] SubTask 5.3: 点击模块名称默认进入该模块工作台

- [x] Task 6: 路由注册
  - [x] SubTask 6.1: 修改 `frontend/src/App.tsx`，注册模块工作台路由
  - [x] SubTask 6.2: `/` 根路由展示团队大盘（已登录）
  - [x] SubTask 6.3: `/workspace` 保留为别名

- [x] Task 7: 测试与验证
  - [x] SubTask 7.1: 运行后端 `pytest -q`
  - [x] SubTask 7.2: 运行前端 `npm run lint`
  - [x] SubTask 7.3: 手动验证：登录后首页展示团队大盘、模块工作台可访问、导航联动正常

# Task Dependencies

- Task 2 depends on Task 1
- Task 3/4 can run in parallel with Task 1-2
- Task 5 depends on Task 4
- Task 6 depends on Task 3-5
- Task 7 depends on Task 1-6
