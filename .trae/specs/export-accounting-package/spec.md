# 记账模式 Step5 真实导出账簿 Spec

## Why

[Step5Export.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/AccountingMode/Step5Export.tsx) 的「导出账簿」按钮仅 `setTimeout(1500)` 后弹「导出成功」，没有任何后端调用，也没有真实文件下载。用户感知到的现象就是「方法失败，没有得到导出文件」。

## What Changes

- 后端新增导出 API：
  - `GET /api/import-jobs/{job_id}/export?format=xlsx|csv|json` 返回真实文件流
  - 内容包括：凭证清单（含 `voucher_no`、`entry_line_no`、日期、科目代码、科目名称、摘要、借方、贷方、对方单位）
- 前端 Step5：
  - 通过 URL `?jobId=` 读取上下文
  - 替换 mock，改为真实 fetch 文件流并触发浏览器下载
  - 缺失 `jobId` 给出明显告警，按钮置灰
- 仅本期支持：`xlsx`、`csv`、`json` 三种格式（`xml` 暂下线，不再展示）。

## Impact

- 受影响 specs：
  - `summarize-requirements`：MVP 流程闭环
  - `entry-line-number`：导出文件包含行号列
- 受影响代码：
  - 新增 `backend/app/api/routes_export.py`
  - 修改 `backend/app/main.py` 注册路由
  - 修改 `frontend/src/pages/AccountingMode/Step5Export.tsx`
  - 修改 `frontend/src/api/client.ts`（增加 `exportImportJob`）

## ADDED Requirements

### Requirement: 真实导出 API

系统 SHALL 提供 `GET /api/import-jobs/{job_id}/export?format=...` 返回真实文件流，`Content-Disposition` 含合理文件名。

#### Scenario: 成功导出 xlsx

- **WHEN** 调用 `GET /api/import-jobs/{job_id}/export?format=xlsx`
- **THEN** 返回 200，`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **AND** 文件包含该 job 的全部分录

#### Scenario: 不支持的格式返回 400

- **WHEN** `format=pdf`
- **THEN** 返回 400，detail 提示支持的格式

#### Scenario: 任务不存在返回 404

- **WHEN** job_id 不存在
- **THEN** 返回 404

### Requirement: 前端 Step5 真实下载

前端 Step5 SHALL fetch 上述 API，把响应 blob 触发浏览器下载，并显示真实成功/失败提示。

#### Scenario: 缺少 jobId 阻止导出

- **WHEN** URL 不带 `jobId`
- **THEN** Step5 显示告警，导出按钮禁用

## MODIFIED Requirements

### Requirement: Step5 导出账簿

不再使用 `setTimeout` 模拟。Step5 SHALL 调用真实导出 API。

## REMOVED Requirements

### Requirement: 导出 XML 格式

**Reason**: 当前业务无 XML 接收方，避免维护成本。
**Migration**: 无；UI 不再展示 XML 选项。
