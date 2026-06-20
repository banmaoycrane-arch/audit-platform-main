# 账套文件管理、客户上下文定位与行业预设科目 Spec

## Why

当前系统已经有团队、账套、项目和基础资料模块，但账套下的文件资料缺少统一管理入口，用户在处理客户资料、原始凭证和后续凭证生成时难以快速定位到具体客户上下文。同时，会计科目设置虽然支持手工维护，但缺少按行业加载预设科目代码的能力，导致用户需要重复录入大量标准科目。

## What Changes

- 在功能模块中增加账套文件管理能力，按账套归集原始凭证、客户资料、合同、发票、银行流水等文件。
- 为文件和客户建立上下文关系，支持基于客户名称、往来单位、文件名、解析摘要快速定位客户。
- 在会计科目设置中增加行业预设科目代码加载能力，避免用户从零手工录入。
- 支持用户选择行业模板后预览科目，再确认导入到账套。
- 保持现有账套、导入任务、会计科目 CRUD 能力不被破坏。

## Impact

- Affected specs:
  - `team-multi-ledger-management`
  - `team-ledger-management-ui`
  - `basic-data-pages`
  - `auto-generate-entries-from-source`
  - `entity-semantic-mapping`
- Affected code:
  - `backend/app/models/ledger.py`
  - `backend/app/db/models.py`
  - `backend/app/api/routes_ledger.py`
  - `backend/app/api/routes_files.py`
  - `backend/app/services/import_service.py`
  - `backend/app/services/coa_service.py`
  - `frontend/src/pages/LedgerManagementPage.tsx`
  - `frontend/src/pages/BasicData/ChartOfAccountsPage.tsx`
  - `frontend/src/api/client.ts`
  - `frontend/src/layout/MainShell.tsx`

## ADDED Requirements

### Requirement: 账套文件管理

The system SHALL provide ledger-level file management for source documents and customer-related files.

#### Scenario: 用户进入账套文件管理
- **WHEN** 用户在账套管理或功能模块中进入文件管理
- **THEN** 系统 SHALL 显示当前账套下的文件列表
- **AND** 文件 SHALL 显示文件名、文件类型、上传时间、解析状态、关联客户或往来单位

#### Scenario: 文件归属到账套
- **WHEN** 用户上传原始凭证、合同、发票、银行流水或客户资料
- **THEN** 文件 SHALL 归属于当前账套
- **AND** 如果当前已有导入任务，文件 MAY 同时关联导入任务

### Requirement: 客户上下文快速定位

The system SHALL infer and display customer context from file metadata, parsed text, counterparty records, and user-provided hints.

#### Scenario: 文件名包含客户名称
- **WHEN** 文件名或解析摘要包含客户名称
- **THEN** 系统 SHALL 尝试匹配现有往来单位或客户档案
- **AND** 页面 SHALL 显示匹配结果和置信说明

#### Scenario: 客户未能自动匹配
- **WHEN** 系统无法从文件名、解析文本或往来单位中确认客户
- **THEN** 页面 SHALL 提供手工选择或新建客户/往来单位入口
- **AND** 用户确认后 SHALL 保存文件与客户上下文的关联

#### Scenario: 用户按客户筛选文件
- **WHEN** 用户在账套文件管理中选择某一客户
- **THEN** 系统 SHALL 只显示该客户相关文件、导入任务和解析摘要

### Requirement: 会计科目行业预设模板

The system SHALL allow users to load predefined chart of accounts templates by industry.

#### Scenario: 用户选择行业预设
- **WHEN** 用户在会计科目设置页面选择一个行业模板
- **THEN** 系统 SHALL 显示该行业的预设科目代码、科目名称、类别、方向和级次
- **AND** 用户 SHALL 能在导入前预览

#### Scenario: 用户确认导入行业科目
- **WHEN** 用户确认导入行业预设科目
- **THEN** 系统 SHALL 将不存在的科目新增到账套科目表
- **AND** 对已存在的科目 SHALL 跳过或提示冲突，不得静默覆盖用户已修改科目

#### Scenario: 用户已有科目数据
- **WHEN** 当前账套已有科目
- **THEN** 系统 SHALL 显示将新增、跳过、冲突的科目数量
- **AND** 用户 SHALL 在确认后再执行导入

## MODIFIED Requirements

### Requirement: 会计科目设置

会计科目设置 SHALL 从单纯手工维护扩展为“手工维护 + 行业预设加载”。行业预设导入不得覆盖已有用户科目，必须提供预览和冲突提示。

### Requirement: 账套管理

账套管理 SHALL 从只管理账套基本信息、生命周期和授权，扩展为能够查看账套文件、客户上下文和文件解析状态。

## REMOVED Requirements

无。
