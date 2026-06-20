# Tasks

## Task 1：建子 spec 三件套
- [x] 1.1 新建 `spec.md`
- [x] 1.2 新建 `tasks.md`
- [x] 1.3 新建 `checklist.md`

## Task 2：后端 Dashboard 接口
- [x] 2.1 新建 `backend/app/api/routes_dashboard.py`，实现 `GET /api/dashboard/summary`
- [x] 2.2 在 `backend/app/main.py` 挂载 `dashboard_router`
- [x] 2.3 新增测试 `backend/tests/test_dashboard_api.py`，包含空库返回 0 / 有数据返回正确计数 两个用例
- [x] 2.4 `pytest backend/tests/test_dashboard_api.py -v` 通过

## Task 3：前端 Dashboard KPI
- [x] 3.1 `frontend/src/api/client.ts` 增加 `getDashboardSummary`
- [x] 3.2 `HomePage.tsx` 顶部增加 4 张 KPI 卡片（antd `Statistic`）
- [x] 3.3 `npm run lint` 通过

## Task 4：审计 Step3 增加序时簿入口
- [x] 4.1 `Step3ImportEntries.tsx` 上传卡片改为 antd `Tabs`，两个 Tab：「凭证导入」/「序时簿导入」
- [x] 4.2 序时簿 Tab 文案明确「按日期连续登记的凭证流水」
- [x] 4.3 `npm run lint` 通过

## Task 5：勾选与收尾
- [x] 5.1 子 spec `tasks.md` / `checklist.md` 全部 [x]
- [x] 5.2 路线图 `next-execution-roadmap/tasks.md` 队列 6 三任务 [x]
- [x] 5.3 路线图 `next-execution-roadmap/checklist.md` 队列 6 全部 [x]
