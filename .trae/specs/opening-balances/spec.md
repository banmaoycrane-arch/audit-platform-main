# 期初科目余额（Opening Balances）Spec

## Why

当前系统缺少"期初余额"录入与查询能力。报表（资产负债表、利润表、科目余额表）的本质是「期初 + 本期发生 = 期末」，没有期初余额一切报表都是从 0 起算，账无法闭合。本 spec 补齐这一块基础能力，并为后续 `financial-statements` 提供数据起点。

## What Changes

- 新增模型 `OpeningBalance`：
  - `id`、`organization_id`、`period_id`（FK accounting_periods）
  - `account_code`（FK chart_of_accounts.code）
  - `debit_balance`（借方期初）、`credit_balance`（贷方期初）
  - `currency`（默认 CNY）
  - `notes`、`created_at`、`updated_at`
  - 唯一约束 `(organization_id, period_id, account_code)`
- 新增服务 `opening_balance_service.py`：
  - `list_by_period(org_id, period_id)`
  - `upsert(org_id, period_id, account_code, debit, credit)`
  - `bulk_upsert(items)`
  - `delete_one(org_id, period_id, account_code)`
  - `trial_balance(org_id, period_id)` 返回借贷合计与是否平衡
- 新增 API：
  - `GET /api/opening-balances?organization_id=&period_id=`
  - `POST /api/opening-balances`（单条 upsert）
  - `POST /api/opening-balances/bulk`（批量 upsert）
  - `DELETE /api/opening-balances/{id}`
  - `GET /api/opening-balances/trial-balance?organization_id=&period_id=`
- 新增前端页面 `BasicData/OpeningBalancesPage.tsx`：
  - 选择组织 + 期间
  - 列出当前期间的所有期初余额（按科目代码升序）
  - 行内编辑借/贷期初余额
  - 显示借贷合计与是否平衡
  - 一键"应用所有一级科目"模板：从 CoA 拉一级科目自动生成空白行
- 在主导航 SAAS Shell 加入「期初余额」入口（路径 `/basic/opening-balances`）

## Impact

- 受影响 specs：
  - `auto-generate-entries-from-source`：会计科目库被作为期初的 catalog
  - `accounting-period-snapshot`：期初余额是期末快照的起点
  - `financial-statements`（未来）：报表的数据来源
- 受影响代码：
  - 新增 `backend/app/db/models.py`（`OpeningBalance`）
  - 新增 `backend/app/services/opening_balance_service.py`
  - 新增 `backend/app/api/routes_opening_balances.py`
  - 修改 `backend/app/main.py` 注册路由
  - 新增 `frontend/src/pages/BasicData/OpeningBalancesPage.tsx`
  - 修改 `frontend/src/api/client.ts`、`frontend/src/App.tsx`、`frontend/src/layout/MainShell.tsx`

## ADDED Requirements

### Requirement: 期初余额数据模型与唯一性

系统 SHALL 持久化期初余额，并对 `(organization_id, period_id, account_code)` 唯一。

#### Scenario: 同期同科目重复录入会更新而非新增
- **WHEN** 用户对同一组织、同一期间、同一科目再次提交期初余额
- **THEN** 后端执行 upsert，仅更新借/贷数值，不新增条目

### Requirement: 期初余额 CRUD 与试算平衡

系统 SHALL 提供 `GET / POST / POST bulk / DELETE` 与 `GET trial-balance`。

#### Scenario: 期初借贷不平衡告警
- **WHEN** 调用 `GET /api/opening-balances/trial-balance`
- **THEN** 返回 `{ debit_total, credit_total, is_balanced }`，并允许前端在不平衡时给出警告

#### Scenario: 删除单条期初
- **WHEN** 调用 `DELETE /api/opening-balances/{id}`
- **THEN** 该条删除，不影响其他科目

### Requirement: 前端期初余额页面

系统 SHALL 提供 `/basic/opening-balances` 页面，支持选择期间、行内编辑、试算平衡可视化。

#### Scenario: 切换期间刷新数据
- **WHEN** 用户切换期间下拉
- **THEN** 表格重新拉取该期间的期初余额

#### Scenario: 显示试算平衡
- **WHEN** 期初余额借贷合计不相等
- **THEN** 顶部 Banner 红色提示「期初借贷不平衡，差额：X」

## MODIFIED Requirements

### Requirement: SAAS Shell 主导航
基础资料下增加「期初余额」入口。

## REMOVED Requirements

无。
