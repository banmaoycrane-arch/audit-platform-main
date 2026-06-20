# 子 Spec：dashboard-home-and-day-book-import

## Why（背景）

1. 当前 `frontend/src/pages/HomePage.tsx` 只是「记账模式 / 审计模式」两张大卡片，会计师进入系统第一眼**没有任何业务量级感受**——本期凭证多少条、有多少未结转期间、还有多少风险待复核、最近又冒了几个审计发现，全都看不到。一个真正可用的财务/审计中后台，首页应当承担「KPI 仪表盘」的角色。
2. 审计模式 Step3（[Step3ImportEntries.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/AuditMode/Step3ImportEntries.tsx)）目前只有一个「凭证导入」的 Dragger，但**审计师从被审计单位拿到的第一份关键证据其实是「序时簿（day book）」**——按日期顺序、连续登记的全部凭证流水，是判断完整性、截止性、是否存在跳号舞弊的最重要原始证据。前端当前没有给序时簿留任何入口。
3. 后端 `ImportJob.source_type` 字段已经存在（默认 `voucher_import`），后端 import 流程可复用，只缺一个区分凭证 / 序时簿的 UI 入口与一个 Dashboard 聚合接口。

## What（实现内容）

### 主题 A — Dashboard KPI

- 后端新增模块 `backend/app/api/routes_dashboard.py`，提供 `GET /api/dashboard/summary?organization_id={int?}`，返回：
  ```json
  {
    "voucher_count": 0,
    "unposted_periods": 0,
    "pending_risks": 0,
    "recent_findings": 0
  }
  ```
  - `voucher_count`：`AccountingEntry.voucher_no` 的 distinct 计数（即凭证张数，不是分录行数）
  - `unposted_periods`：`AccountingPeriod.status == "open"` 数量（=未结账期间）
  - `pending_risks`：`AuditRisk.status == "pending_review"` 数量
  - `recent_findings`：`AuditFinding` 总数（占位，后续可改成最近 30 天）
- `main.py` 注册 `dashboard_router`。
- 前端 `client.ts` 增加 `getDashboardSummary(organizationId?)`。
- `HomePage.tsx` 在标题下方、两张大卡片上方，增加一行 4 个 KPI 卡片（凭证数 / 未结转期间 / 待复核风险 / 最近审计发现）；通过 `useEffect` 调接口，失败时默认 0 不阻塞页面。

### 主题 B — 序时簿（day book）导入入口

- 不新增后端接口（复用 `import-jobs` 流程），后端 `ImportJob.source_type` 已支持自定义值。
- 前端 `Step3ImportEntries.tsx` 改造：
  - 上传卡片改为 antd `Tabs`，包含「凭证导入」和「序时簿导入」两个 Tab；每个 Tab 内仍是一个 Dragger
  - 序时簿 Tab 的 `ant-upload-hint` 文案明确写「序时簿：按日期顺序、连续登记的全部凭证流水。请保留凭证号、日期、借贷、对方单位等列」
  - 两个 Tab 共享底部的「已导入分录」表格
  - 由于本步进入时 `ImportJob` 已在 Step2 创建，本期暂不真正区分 `source_type` 落库；只在前端入口处给出明确语义，留给后续 spec 把 `source_type=audit_day_book` 透传至后端

## ADDED Requirements

- 首页有 4 个 KPI 卡片，数字来自后端实时统计
- 审计 Step3 给序时簿留出独立 UI 入口（即使后端复用）
- `GET /api/dashboard/summary` 接口在空数据库下也返回 4 个 0 而非报错

## 受影响代码

- 新增 `backend/app/api/routes_dashboard.py`
- 修改 `backend/app/main.py`（挂载路由）
- 新增 `backend/tests/test_dashboard_api.py`
- 修改 `frontend/src/pages/HomePage.tsx`
- 修改 `frontend/src/pages/AuditMode/Step3ImportEntries.tsx`
- 修改 `frontend/src/api/client.ts`

## 不在范围（Out of Scope）

- 不真正在数据库 `ImportJob.source_type` 写入 `audit_day_book`（避免影响 Step2 现有创建逻辑）
- 不做真正的「最近 30 天」时间过滤，`recent_findings` 当前是总数
- 不做组织/期间多选下拉过滤，`organization_id` 是可选 query
