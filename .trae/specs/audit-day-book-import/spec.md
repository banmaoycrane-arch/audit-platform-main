# 审计模式「导入序时簿模式」Spec

## Why

审计师从被审计单位获取的关键审计证据之一是「序时簿（day book）」——按日期顺序、连续登记的全部凭证流水。当前审计模式 Step3 已支持「凭证导入」和「序时簿导入」两个 UI Tab（`dashboard-home-and-day-book-import` spec 已完成），但两者在后端处理逻辑上完全复用凭证导入流程，没有真正区分序时簿的语义。

在审计实务中，序时簿与凭证导入有本质区别：
- **凭证导入**：被审计单位已整理好的凭证文件，通常包含凭证号、日期、科目、借贷金额等
- **序时簿导入**：按日期顺序连续登记的原始流水，可能包含大量未整理的分录，需要系统按凭证号分组、识别完整性、检测跳号

因此需要：
1. 后端真正区分 `source_type=audit_day_book`，在导入时执行序时簿特有的处理逻辑（按凭证号分组、完整性校验、跳号检测）
2. 前端在导入时传递 `source_type` 参数，让后端知道当前导入的是序时簿
3. 序时簿导入完成后，提供序时簿特有的审计视图（如按日期排序、凭证号连续性检测、跳号提示）

## What Changes

- 后端修改：
  - `ImportJob.source_type` 字段已存在，当前默认 `voucher_import`。需要让 `routes_imports.py` 在创建导入任务时支持传入 `source_type`
  - `import_service.py` 的 `process_import_job` 函数增加对 `source_type=audit_day_book` 的分支处理：
    - 按 `voucher_no` 分组，将同一凭证号的多行分录合并为一个凭证
    - 执行完整性校验：检测凭证号是否连续、是否有缺失
    - 生成跳号检测报告
  - 新增 `audit_day_book_service.py`：序时簿专用处理逻辑
- 前端修改：
  - `Step3ImportEntries.tsx` 在调用 `api.createImportJob` 时传入 `source_type` 参数（当前 Step2 创建 job 时未传）
  - 序时簿 Tab 导入完成后，展示序时簿特有的检测信息（跳号、完整性）
- 新增 API：
  - `GET /api/import-jobs/{job_id}/day-book-report`：获取序时簿导入的检测报告（跳号、完整性）
- 新增测试：
  - `test_audit_day_book_api.py`：覆盖序时簿导入、检测报告

## Impact

- 影响的 specs：
  - `dashboard-home-and-day-book-import`：序时簿 UI 入口已存在，本 spec 补齐后端语义
  - `audit-step3-real-entries`：Step3 已接入真实分录，本 spec 增加序时簿模式
  - `adaptive-import-engine`：复用自适应导入引擎，增加序时簿模板识别
- 影响的代码：
  - 后端：`routes_imports.py`、`import_service.py`、新增 `audit_day_book_service.py`
  - 前端：`Step3ImportEntries.tsx`、`client.ts`
  - 测试：新增 `test_audit_day_book_api.py`

## ADDED Requirements

### Requirement: 序时簿导入模式

系统 SHALL 支持审计模式下的序时簿导入，与凭证导入在语义和处理逻辑上区分。

#### Scenario: 创建序时簿导入任务

- **WHEN** 用户在审计模式 Step3 选择「序时簿导入」Tab 并上传文件
- **THEN** 前端创建导入任务时传入 `source_type="audit_day_book"`
- **AND** 后端 `ImportJob.source_type` 存储为 `audit_day_book`

#### Scenario: 序时簿解析与分组

- **WHEN** 后端处理 `source_type=audit_day_book` 的导入任务
- **THEN** 按 `voucher_no` 将多行分录分组为凭证
- **AND** 每个凭证的借贷金额必须平衡（借方合计 = 贷方合计）
- **AND** 不平衡的凭证标记为异常，生成检测报告

#### Scenario: 序时簿完整性检测

- **WHEN** 序时簿导入完成
- **THEN** 系统检测凭证号的连续性
- **AND** 识别缺失的凭证号（跳号）
- **AND** 生成跳号检测报告，包含：起始凭证号、结束凭证号、缺失凭证号列表

#### Scenario: 序时簿检测报告展示

- **WHEN** 用户完成序时簿导入
- **THEN** 前端展示序时簿检测报告
- **AND** 报告包含：凭证总数、跳号数量、不平衡凭证数量、完整性评分

## MODIFIED Requirements

### Requirement: 导入任务创建接口

`POST /api/import-jobs` SHALL 支持可选参数 `source_type`，默认值为 `voucher_import`。

### Requirement: 导入任务处理逻辑

`process_import_job` SHALL 根据 `job.source_type` 选择处理分支：
- `voucher_import`：现有逻辑，直接解析为分录
- `audit_day_book`：调用序时簿专用处理逻辑，执行分组、平衡校验、完整性检测

## REMOVED Requirements

无。
