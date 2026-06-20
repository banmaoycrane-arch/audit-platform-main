# Tasks（路线图调度）

## 队列 1：period-close-pl-transfer
- [x] 已完成（service / API / 前端按钮 / pytest 3 用例 / 前端 lint 通过）
- 文件：`backend/app/services/period_close_service.py`、`backend/app/api/routes_accounting_periods.py`、`frontend/src/pages/AccountingPeriodsPage.tsx`、`backend/tests/test_period_close_pl_transfer.py`

## 队列 2：accounting-step4-real-review（spec 缺失，需新建）
- [x] Task 2.1：新建 `.trae/specs/accounting-step4-real-review/{spec,tasks,checklist}.md`
  - 一句话目标：将 [Step4ReviewEntries.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/AccountingMode/Step4ReviewEntries.tsx) 的 mockEntries 替换为真实草稿（来自 Step3 的 `generate-entries` 返回值）+ 真实 commit
  - 范围：URL 通过 `?jobId=&periodId=` 携带；编辑后调用 `commitEntries`；保留行内编辑、批量复核
- [x] Task 2.2：实施（在新 spec 内进行）
- [x] Task 2.3：验证（pytest + 前端 lint）

## 队列 3：audit-report-export（spec 缺失，需新建）
- [x] Task 3.1：新建 `.trae/specs/audit-report-export/{spec,tasks,checklist}.md`
  - 一句话目标：审计模式 Step6 导出真实审计报告（含审计发现、测试结果、循环断裂、内控预警），格式 docx + xlsx
  - 范围：后端新 `routes_audit_export.py` + 前端 Step6 替换 mock 下载
- [x] Task 3.2：实施
- [x] Task 3.3：验证

## 队列 4：business-cycle-audit（spec 已有）
- 现状：Task 1–4 完成；剩 Task 5（API）+ Task 6（测试）
- [x] Task 4.5：API 接口开发（参见 [tasks.md#Task5](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/business-cycle-audit/tasks.md)）
  - `GET /api/business-cycles`（按组织/期间过滤）
  - `POST /api/business-cycles/detect-breaks`
  - `GET /api/business-cycles/{id}/risks`（循环后风险）
- [x] Task 4.6：单测 + 集成测试（覆盖率 ≥ 80%）

## 队列 5：internal-control-audit（spec 已有）
- 现状：Task 1–4 完成；剩 Task 5（API）+ Task 6（测试）
- [x] Task 5.5：API 接口开发（参见 [tasks.md#Task5](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/internal-control-audit/tasks.md)）
  - `GET /api/internal-controls`
  - `POST /api/internal-controls/test`
  - `GET /api/internal-controls/alerts`
- [x] Task 5.6：单测 + 集成测试

## 队列 6：dashboard-home-and-day-book-import（spec 缺失，需新建）
- [x] Task 6.1：新建 `.trae/specs/dashboard-home-and-day-book-import/{spec,tasks,checklist}.md`
  - 主题 A：首页 Dashboard 改造（KPI 卡片：本期凭证数、未结转期间、未复核风险、最近审计发现）
  - 主题 B：审计模式 Step3 增加「导入序时簿」入口（与现有「凭证导入」并列），复用 import-jobs，但 source_type=audit_day_book
- [x] Task 6.2：实施（前后端）
- [x] Task 6.3：验证

# Task Dependencies

- 队列 2 → 队列 3 → 队列 4 → 队列 5 → 队列 6（按用户给定顺序串行）
- 每个缺失 spec 的队列，必须先完成 Task X.1（新建子 spec 文档），才能进入 Task X.2（实施）

# 完成定义（DoD，每个队列共用）

- 后端 `pytest` 该模块测试通过
- 前端 `npm run lint`（即 `tsc --noEmit`）无错误
- 对应 spec 的 `checklist.md` 全部 checkbox 勾选
- 本 roadmap 的 `tasks.md` 对应 checkbox 勾选，并在 PR 描述里链接
