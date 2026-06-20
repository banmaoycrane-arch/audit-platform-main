# Tasks

- [x] Task 1: 后端团队管理 API 扩展
  - [x] SubTask 1.1: 修改 `backend/app/services/ledger_management_service.py` — 增加团队查询、创建团队方法
  - [x] SubTask 1.2: 新增 `backend/app/api/routes_team.py` — 团队管理端点：POST /api/teams（创建）, GET /api/teams（列表）, GET /api/teams/{id}/members（成员列表）, POST /api/teams/{id}/members（添加成员）
  - [x] SubTask 1.3: 在 `main.py` 注册 team 路由

- [x] Task 2: 后端用户授权查询 API
  - [x] SubTask 2.1: 修改 `backend/app/api/routes_ledger.py` — 增加 GET /api/ledgers/{id}/auths（查询账套授权列表）
  - [x] SubTask 2.2: 修改 `backend/app/api/routes_ledger.py` — 增加 DELETE /api/ledgers/{id}/auths/{auth_id}（撤销授权）

- [x] Task 3: 前端团队管理页面
  - [x] SubTask 3.1: 新增 `frontend/src/pages/TeamManagementPage.tsx` — 团队列表、创建团队、管理团队人员
  - [x] SubTask 3.2: 新增 `frontend/src/api/client.ts` — 团队 API 方法（createTeam, listTeams, getTeamMembers, addTeamMember）

- [x] Task 4: 前端账套管理页面
  - [x] SubTask 4.1: 新增 `frontend/src/pages/LedgerManagementPage.tsx` — 账套列表、创建账套、生命周期管理、授权管理
  - [x] SubTask 4.2: 修改 `frontend/src/api/client.ts` — 账套授权 API 方法（getLedgerAuths, revokeLedgerAuth）

- [x] Task 5: 前端登录后引导流程
  - [x] SubTask 5.1: 修改 `frontend/src/pages/LoginPage.tsx` — 登录成功后检查用户团队/账套状态
  - [x] SubTask 5.2: 新增 `frontend/src/pages/OnboardingPage.tsx` — 首次登录引导页面（创建团队 → 创建账套）
  - [x] SubTask 5.3: 在 `App.tsx` 注册 onboarding 路由

- [x] Task 6: 前端工作台管理入口
  - [x] SubTask 6.1: 修改 `frontend/src/pages/WorkspacePage.tsx` — 用户下拉菜单增加"团队管理"、"账套管理"、"项目管理"
  - [x] SubTask 6.2: 修改 `frontend/src/layout/MainShell.tsx` — 顶部导航增加管理入口（可选）

- [x] Task 7: 测试与验证
  - [x] SubTask 7.1: 新增 `backend/tests/test_team_api.py` — 团队创建、成员管理测试
  - [x] SubTask 7.2: 运行后端 `pytest -q`
  - [x] SubTask 7.3: 运行前端 `npm run lint`

# Task Dependencies

- Task 2 depends on Task 1
- Task 3-4 can run in parallel with Task 1-2
- Task 5 depends on Task 3-4
- Task 6 depends on Task 5
- Task 7 depends on Task 1-6
