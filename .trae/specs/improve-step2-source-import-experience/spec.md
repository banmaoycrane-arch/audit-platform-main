# 凭证管理 Step2 原始凭证导入体验优化 Spec

## Why

当前凭证管理 Step2「导入原始资料」页面虽然提供了原始资料类型辅助信息、文件上传和会计期间选择，但用户缺少与系统解析结果的实质性互动，无法判断上传资料是否被识别、识别了什么、是否足以生成凭证草稿。会计期间选择也过于简陋，未充分利用凭证日期和期间规则自动推断期间，影响财务人员的使用效率和业务判断。

## What Changes

- 优化「提供原始资料类型辅助信息」：从静态勾选说明升级为参与解析反馈的业务辅助信息。
- 优化「上传原始凭证文件」控件：缩小上传控件视觉占比，增加文件解析状态、解析摘要、识别资料类型、缺失资料提示和下一步建议。
- 优化「选择会计期间」：根据当前日期、凭证日期、已有会计期间自动推荐默认期间。
- 优化会计期间填写界面：期间编码、期间类型、开始日期、结束日期形成联动，而不是孤立输入。
- 保持现有 AI 生成凭证流程，不改变 Step3 生成凭证草稿的核心接口。

## Impact

- Affected specs:
  - `auto-generate-entries-from-source`
  - `unify-voucher-input-modes`
  - `govern-ai-voucher-evidence-tags`
  - `accounting-period-snapshot`
- Affected code:
  - `frontend/src/pages/AccountingMode/Step2ImportSource.tsx`
  - `frontend/src/pages/AccountingMode/Step3GenerateEntries.tsx`
  - `frontend/src/api/client.ts`
  - `backend/app/api/routes_imports.py`
  - `backend/app/services/import_service.py`
  - `backend/app/services/source_document_service.py`
  - `backend/app/api/routes_accounting_periods.py`
  - `backend/app/services/accounting_period_service.py`

## ADDED Requirements

### Requirement: 原始资料类型辅助信息必须参与解析反馈

The system SHALL use selected source document type hints as user-provided context for source document recognition and display whether uploaded files match those hints.

#### Scenario: 用户勾选发票并上传 PDF
- **WHEN** 用户在 Step2 勾选「发票」并上传 PDF 文件
- **THEN** 系统 SHALL 显示该文件的上传状态和解析状态
- **AND** 系统 SHALL 显示识别出的资料类型是否与「发票」匹配
- **AND** 如果无法确认资料类型，系统 SHALL 提示「系统未能确认该文件是否为发票，请检查文件内容或补充资料类型说明」

#### Scenario: 用户勾选多个资料类型
- **WHEN** 用户勾选发票、银行流水、合同等多个资料类型
- **THEN** 系统 SHALL 将这些类型作为 AI 识别辅助信息展示在文件解析结果旁
- **AND** 系统 SHALL 说明每类资料在凭证生成中的证据作用

### Requirement: 上传文件必须有解析过程反馈

The system SHALL provide visible parsing feedback after source document upload.

#### Scenario: 文件上传成功后进入解析
- **WHEN** 用户上传原始凭证文件成功
- **THEN** 页面 SHALL 显示「已上传」「解析中」「解析完成」或「解析失败」状态
- **AND** 解析完成后 SHALL 显示文件名、文件类型、识别资料类型、识别摘要、可提取的日期/金额/对方单位等关键字段

#### Scenario: 文件解析失败
- **WHEN** 文件上传成功但解析失败
- **THEN** 页面 SHALL 显示失败原因
- **AND** 页面 SHALL 提供重新上传、改为人工录入或继续补充其他资料的入口

### Requirement: 上传控件应适配财务工作台页面密度

The system SHALL reduce the visual size of the upload control and reserve more space for parsed document feedback.

#### Scenario: Step2 页面展示上传区域
- **WHEN** 用户进入 Step2 导入原始资料页面
- **THEN** 上传控件 SHALL 使用紧凑型样式
- **AND** 页面 SHALL 将主要空间用于文件列表、解析状态和业务反馈

### Requirement: 会计期间应根据日期自动推荐

The system SHALL recommend an accounting period based on current date, voucher date, and existing accounting periods.

#### Scenario: 当前日期落入已有打开期间
- **WHEN** 用户进入 Step2 且存在覆盖当前日期的 open 或 reopened 会计期间
- **THEN** 系统 SHALL 默认选择该期间

#### Scenario: 凭证日期落入已有期间
- **WHEN** 用户填写或系统识别出凭证日期
- **THEN** 系统 SHALL 优先推荐覆盖该凭证日期的会计期间

#### Scenario: 不存在匹配期间
- **WHEN** 当前日期或凭证日期没有匹配的会计期间
- **THEN** 系统 SHALL 根据日期建议新期间编码、期间类型、开始日期和结束日期
- **AND** 用户 SHALL 能确认创建该期间

### Requirement: 会计期间填写字段必须联动

The system SHALL derive accounting period code from period type, start date, and end date unless user manually overrides it.

#### Scenario: 用户选择月度期间
- **WHEN** 用户选择期间类型为「月度」并选择 2026-06 的日期范围
- **THEN** 系统 SHALL 默认生成期间编码 `2026-06`
- **AND** 开始日期 SHALL 默认为当月第一天
- **AND** 结束日期 SHALL 默认为当月最后一天

#### Scenario: 用户选择年度期间
- **WHEN** 用户选择期间类型为「年度」并选择 2026 年
- **THEN** 系统 SHALL 默认生成期间编码 `2026`
- **AND** 开始日期 SHALL 默认为 2026-01-01
- **AND** 结束日期 SHALL 默认为 2026-12-31

## MODIFIED Requirements

### Requirement: Step2 AI 原始资料上传流程

Step2 SHALL no longer treat source document type selection as a static decoration. It SHALL combine selected source type hints, uploaded file parsing status, and accounting period recommendation into one coherent workflow before entering Step3 AI voucher draft generation.

### Requirement: 会计期间选择

Accounting period selection SHALL be changed from a simple manual selector/input to a date-driven period recommendation and confirmation flow. Period code SHALL be derived from period type and date range by default.

## REMOVED Requirements

无。
