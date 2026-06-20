# 审计模式 Step3 真实分录导入 Spec

## Why

审计模式 Step4 与 Step5 已接入真实审计测试 API，但 Step3「导入被审计单位会计分录」仍使用 mock 数据。这导致整个审计模式实际上没有"被审计单位账"作为输入，Step4 的审计测试与 Step5 的审计发现无法对应真实数据，审计结论缺乏证据支撑。

## What Changes

- 前端 `Step3ImportEntries.tsx` 替换 mock 数据：
  - 支持上传被审计单位凭证文件（Excel/CSV）
  - 复用 Step2 已创建的 `jobId`（通过 URL `?jobId=` 流转）
  - 调用 `POST /api/import-jobs/{jobId}/files` 上传凭证
  - 调用 `POST /api/import-jobs/{jobId}/process/sync` 同步解析
  - 调用 `GET /api/entries?import_job_id={jobId}` 拉取真实分录
  - 列表中显示 `voucher_no` + `entry_line_no`
  - 通过查询参数把 `jobId` 传递到 Step4
- 后端 `/api/import-jobs/{id}/process/sync` 当前 `response_model=ImportJobRead` 但实际返回 `{job, report}`，会触发 ResponseValidationError。需要去除/调整 `response_model` 让响应可序列化为前端可用结构。
- 不引入新数据库表，不引入新 API 端点（仅修复一个已存在端点的响应类型）。

## Impact

- 影响的 specs：
  - `summary-library`：Step3 是审计模式 6 步引导的关键步骤
  - `adaptive-import-engine`：被审计单位凭证导入复用现有自适应引擎
  - `entry-line-number`：复用 `entry_line_no` 显示
- 影响的代码：
  - 前端 `frontend/src/pages/AuditMode/Step3ImportEntries.tsx`
  - 前端 `frontend/src/api/client.ts`（如需补辅助方法）
  - 后端 `backend/app/api/routes_imports.py`（修复 `process/sync` 响应）

## ADDED Requirements

### Requirement: 审计模式 Step3 接入真实分录导入

系统 SHALL 允许用户在审计模式 Step3 中上传被审计单位的会计凭证文件，调用真实导入流程并展示真实分录。

#### Scenario: 上传 CSV 凭证并展示真实分录

- **WHEN** 用户在 Step3 上传被审计单位的 CSV 凭证文件
- **THEN** 前端调用 `POST /api/import-jobs/{jobId}/files` 上传成功
- **AND** 前端调用 `POST /api/import-jobs/{jobId}/process/sync` 解析成功
- **AND** 前端调用 `GET /api/entries?import_job_id={jobId}` 拉取真实分录
- **AND** 列表展示 `voucher_no` 与 `entry_line_no`

#### Scenario: jobId 在 Step3 与 Step4 之间正确流转

- **WHEN** Step3 完成真实分录导入
- **THEN** 点击下一步进入 Step4 时 URL 包含 `?jobId={jobId}`
- **AND** Step4 能基于该 jobId 调用真实审计测试 API

### Requirement: 不再使用 mock 分录

Step3 SHALL 不再使用硬编码的 mockEntries 列表。

#### Scenario: 未上传文件时显示空状态

- **WHEN** 用户进入 Step3 且未上传任何分录文件
- **THEN** 列表为空且提示用户上传分录

## MODIFIED Requirements

### Requirement: `/api/import-jobs/{id}/process/sync` 响应类型

该端点 SHALL 返回 `{ job: ImportJobRead, report: ... }` 结构，且响应不再受 `response_model=ImportJobRead` 强校验，避免返回结构不匹配导致 `ResponseValidationError`。

## REMOVED Requirements

无。
