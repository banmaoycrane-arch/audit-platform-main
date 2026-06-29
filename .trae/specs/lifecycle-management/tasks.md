# Tasks

- [x] Task 1: 后端 Ledger 生命周期字段扩展
  - [x] SubTask 1.1: 修改 `backend/app/models/ledger.py` — 增加 status, activated_at, suspended_at, archived_at, deleted_at, lifecycle_reason
  - [x] SubTask 1.2: 修改 `backend/app/services/ledger_management_service.py` — 增加生命周期转换方法（activate, suspend, archive, restore）
  - [x] SubTask 1.3: 修改 `backend/app/api/routes_ledger.py` — 增加生命周期操作端点（POST /{id}/activate, POST /{id}/suspend, POST /{id}/archive, POST /{id}/restore）

- [x] Task 2: 后端 Project 生命周期字段扩展
  - [x] SubTask 2.1: 修改 `backend/app/models/project.py` — 增加 status, completed_at, cancelled_at, lifecycle_reason
  - [x] SubTask 2.2: 修改 `backend/app/services/project_service.py` — 增加生命周期转换方法（start, pause, complete, reopen, cancel）
  - [x] SubTask 2.3: 修改 `backend/app/api/routes_project.py` — 增加生命周期操作端点

- [x] Task 3: 后端生命周期事件日志
  - [x] SubTask 3.1: 新增 `backend/app/models/lifecycle_log.py` — LifecycleLog 模型
  - [x] SubTask 3.2: 新增 `backend/app/services/lifecycle_service.py` — 记录生命周期事件
  - [x] SubTask 3.3: 新增 `backend/app/api/routes_lifecycle.py` — 查询生命周期日志端点

- [x] Task 4: 前端生命周期状态展示
  - [x] SubTask 4.1: 修改 `frontend/src/components/LedgerSelector.tsx` — 显示账簿生命周期状态（Tag 颜色区分）
  - [x] SubTask 4.2: 修改 `frontend/src/pages/ProjectsPage.tsx` — 显示项目生命周期状态，增加状态操作按钮
  - [x] SubTask 4.3: 新增 `frontend/src/pages/LedgerLifecyclePage.tsx` — 账簿生命周期管理页面

- [x] Task 5: 测试与验证
  - [x] SubTask 5.1: 新增 `backend/tests/test_lifecycle.py` — 生命周期转换测试
  - [x] SubTask 5.2: 运行后端 `pytest -q`
  - [x] SubTask 5.3: 运行前端 `npm run lint`

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 can run in parallel with Task 1-2
- Task 4 depends on Task 1-3
- Task 5 depends on Task 1-4
