# Tasks

- [x] Task 1: 后端账套模型与授权模型
  - [x] SubTask 1.1: 新增 `backend/app/models/ledger.py` — Ledger 模型（id, name, team_id, status, database_url预留, created_at, updated_at）
  - [x] SubTask 1.2: 新增 `backend/app/models/user_ledger_auth.py` — UserLedgerAuth 模型（user_id, ledger_id, role, granted_at, granted_by）
  - [x] SubTask 1.3: 修改 `backend/app/models/user.py` — 增加 `last_ledger_id` 字段和 `ledger_auths` relationship
  - [x] SubTask 1.4: 修改 `backend/app/models/team.py` — 增加 `ledgers` relationship
  - [x] SubTask 1.5: 在 `models/__init__.py` 导入新模型
  - [x] SubTask 1.6: 数据库自动建表（SQLite 兼容）

- [x] Task 2: 后端业务表增加 ledger_id
  - [x] SubTask 2.1: 修改 `AccountingEntry` 模型 — 增加 `ledger_id`（nullable，兼容旧数据）
  - [x] SubTask 2.2: 修改 `AccountingPeriod` 模型 — 增加 `ledger_id`
  - [x] SubTask 2.3: 修改 `ImportJob` 模型 — 增加 `ledger_id`
  - [x] SubTask 2.4: 修改其他关键业务表（PeriodSnapshot, AuditTest, RiskFinding 等）— 增加 `ledger_id`
  - [x] SubTask 2.5: 确保现有测试不因新增字段而失败（nullable 或默认值）

- [x] Task 3: 后端账套管理 API
  - [x] SubTask 3.1: 新增 `backend/app/services/ledger_service.py` — 创建账套、授权用户、切换账套、获取用户账套列表
  - [x] SubTask 3.2: 新增 `backend/app/api/routes_ledger.py` — POST /api/ledgers（创建）, GET /api/ledgers（列表）, POST /api/ledgers/{id}/switch（切换）, POST /api/ledgers/{id}/auth（授权）
  - [x] SubTask 3.3: 修改 `backend/app/api/routes_dashboard.py` — 所有查询增加 ledger_id 过滤
  - [x] SubTask 3.4: 在 `main.py` 注册 ledger 路由

- [x] Task 4: 后端认证中间件扩展
  - [x] SubTask 4.1: 修改 `backend/app/core/dependencies.py` — `get_current_user` 返回用户 + 当前账套
  - [x] SubTask 4.2: 新增 `get_current_ledger` 依赖 — 从请求 Header 或 Token 中获取当前账套 ID
  - [x] SubTask 4.3: 验证用户是否有当前账套的访问权限

- [x] Task 5: 前端账套选择器与状态管理
  - [x] SubTask 5.1: 修改 `frontend/src/stores/authStore.ts` — 增加 `currentLedgerId`, `setCurrentLedger`, `userLedgers` 列表
  - [x] SubTask 5.2: 修改 `frontend/src/api/client.ts` — 新增 ledger API 方法（create, list, switch, auth）
  - [x] SubTask 5.3: 新增 `frontend/src/components/LedgerSelector.tsx` — 账套选择器组件（Dropdown 或 Select）
  - [x] SubTask 5.4: 登录后自动获取用户账套列表，如果有默认账套自动进入

- [x] Task 6: 前端首页与工作台改造
  - [x] SubTask 6.1: 修改 `frontend/src/pages/WorkspacePage.tsx` — 顶部增加账套选择器 + 团队名称 + 用户名称
  - [x] SubTask 6.2: 大盘数据根据当前账套过滤显示
  - [x] SubTask 6.3: 切换账套后自动刷新页面数据
  - [x] SubTask 6.4: 如果用户无授权账套，显示"请联系管理员分配账套"

- [x] Task 7: 测试与验证
  - [x] SubTask 7.1: 新增 `backend/tests/test_ledger_api.py` — 创建账套、授权、切换、数据隔离
  - [x] SubTask 7.2: 运行后端 `pytest -q`
  - [x] SubTask 7.3: 运行前端 `npm run lint`
  - [x] SubTask 7.4: 手动验证：登录后选择账套、切换账套数据隔离、默认账套自动进入

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 1-2
- Task 4 depends on Task 3
- Task 5 can run in parallel with Task 1-4
- Task 6 depends on Task 5
- Task 7 depends on Task 1-6
