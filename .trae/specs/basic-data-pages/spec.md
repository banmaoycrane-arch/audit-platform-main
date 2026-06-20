# 基础资料前端页面 Spec

## Why

后端已有会计科目（CoA）、对方单位（Counterparty）、会计期间（AccountingPeriod）、风险（AuditRisk）、分录（AccountingEntry）等 API，但前端仅记账/审计两个向导，缺少「基础资料」一类的常驻页面。

## What Changes

- 新增 `BasicData/ChartOfAccountsPage.tsx`：会计科目列表 + 新增/停用/作废/删除
- 新增 `BasicData/CounterpartiesPage.tsx`：对方单位列表 + 新增/停用
- 新增 `AccountingPeriodsPage.tsx`：会计期间列表 + 新增
- 新增 `WorkspacePage.tsx`：工作台 KPI + 快速入口
- 这些页面在 SAAS Shell 内通过左侧导航访问

## Impact

- 修改：`frontend/src/App.tsx`（嵌套路由）
- 新增：上述 4 个页面文件 + `EntriesPageRoute`、`RisksPageRoute` 包装

## ADDED Requirements

### Requirement: 会计科目页面
- 列表展示代码/名称/类别/方向/级次/系统标记/状态
- 新增自定义科目；系统科目不可硬删

### Requirement: 对方单位页面
- 列表展示并支持新增、停用

### Requirement: 会计期间页面
- 列表展示并支持新增

### Requirement: 工作台页面
- 显示导入任务数/分录数/风险数 + 快速入口

## MODIFIED / REMOVED
无。
