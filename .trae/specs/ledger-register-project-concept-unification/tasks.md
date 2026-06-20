# Tasks

- [x] Task 1: 后端项目模型创建
  - [x] SubTask 1.1: 新增 `backend/app/models/project.py` — Project 模型（id, name, team_id, type, status, start_date, end_date, manager_id, created_at, updated_at）
  - [x] SubTask 1.2: 新增 `backend/app/models/project_ledger.py` — ProjectLedger 关联模型（project_id, ledger_id）
  - [x] SubTask 1.3: 新增 `backend/app/models/project_member.py` — ProjectMember 关联模型（project_id, user_id, role）
  - [x] SubTask 1.4: 在 `models/__init__.py` 导入新模型
  - [x] SubTask 1.5: 数据库自动建表

- [x] Task 2: 后端项目管理 API
  - [x] SubTask 2.1: 新增 `backend/app/services/project_service.py` — 创建项目、关联账套、分配人员、查询项目列表
  - [x] SubTask 2.2: 新增 `backend/app/api/routes_project.py` — 端点：
    - POST /api/projects（创建项目）
    - GET /api/projects（项目列表）
    - POST /api/projects/{id}/ledgers（关联账套）
    - POST /api/projects/{id}/members（分配人员）
  - [x] SubTask 2.3: 在 `main.py` 注册 project 路由

- [x] Task 3: 前端模块内台账入口
  - [x] SubTask 3.1: 修改银行模块工作台 — 增加"资金收支台账"、"银行对账台账"入口
  - [x] SubTask 3.2: 修改税务模块工作台 — 增加"发票开具台账"、"认证抵扣台账"入口
  - [x] SubTask 3.3: 修改进销存模块工作台 — 增加"库存收发台账"入口
  - [x] SubTask 3.4: 修改固定资产模块工作台 — 增加"资产增减台账"入口

- [x] Task 4: 前端项目概念引入
  - [x] SubTask 4.1: 修改首页工作台 — 增加"项目管理"入口卡片
  - [x] SubTask 4.2: 新增 `frontend/src/pages/ProjectsPage.tsx` — 项目列表页面
  - [x] SubTask 4.3: 新增项目 API 方法到 `client.ts`

- [x] Task 5: 测试与验证
  - [x] SubTask 5.1: 新增 `backend/tests/test_project_api.py` — 创建项目、关联账套、分配人员
  - [x] SubTask 5.2: 运行后端 `pytest -q`
  - [x] SubTask 5.3: 运行前端 `npm run lint`

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 can run in parallel with Task 1-2
- Task 4 depends on Task 2
- Task 5 depends on Task 1-4
