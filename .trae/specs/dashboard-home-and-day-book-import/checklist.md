# Checklist

## 后端
- [x] `routes_dashboard.py` 含 `GET /api/dashboard/summary`
- [x] `main.py` 挂载 `dashboard_router`
- [x] 空库下接口返回 `voucher_count=0 / unposted_periods=0 / pending_risks=0 / recent_findings=0`
- [x] 有数据时返回正确计数
- [x] `pytest backend/tests/test_dashboard_api.py -v` 通过

## 前端
- [x] `client.ts` 含 `getDashboardSummary`
- [x] `HomePage` 顶部展示 4 张 KPI 卡片
- [x] 审计 Step3 含「凭证导入 / 序时簿导入」Tabs
- [x] 序时簿 Tab 文案体现"按日期连续登记的凭证流水"
- [x] `npm run lint` 通过

## 文档
- [x] 子 spec 三件套全部存在
- [x] 路线图 `tasks.md` 队列 6 全部勾选
- [x] 路线图 `checklist.md` 队列 6 全部勾选
