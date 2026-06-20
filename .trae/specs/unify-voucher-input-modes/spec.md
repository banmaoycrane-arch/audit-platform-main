# 财务总账凭证管理统一输入模式 Spec

## Why

当前「财务总账 / 凭证管理 / 选择原始资料」更像是在选择原始资料类型，例如发票、银行流水、合同等。但从会计实务看，这个卡片真正需要表达的是「凭证输入路径」：一种是根据原始资料由 AI 自主识别并自动生成凭证，另一种是传统人工录入凭证。

这两种方式只是输入路径不同，最终交付产物必须一致：都应形成统一、标准、可复核、可导出、符合国家会计信息化管理要求的会计标准凭证。

## What Changes

- 将凭证管理 Step1 从「选择原始资料类型」调整为「选择凭证输入模式」。
- 保留两条输入路径：
  - AI 智能生成路径：上传原始资料，由系统识别资料类型、提取关键信息、生成会计凭证草稿。
  - 人工录入路径：保留传统手工录入凭证方式，由用户直接填写凭证头和分录行。
- 两条路径最终统一进入同一个标准凭证复核流程。
- 两条路径最终都落库为同一套 `AccountingEntry` / 凭证分录结构。
- 不因输入路径不同生成两套凭证模型，避免后续报表、审计、导出逻辑分裂。
- 前端需要清晰提示：AI 生成是提高效率的智能路径，人工录入是保底和传统兼容路径。

## Impact

- Affected specs:
  - `auto-generate-entries-from-source`：已有 AI 自动生成分录能力，本次调整入口语义与流程组织。
  - `restore-voucher-management-step-flow`：已有财务总账凭证管理 Step 流程，本次修改 Step1 和分支路径。
  - `export-accounting-package`：最终导出的仍是统一标准凭证。
  - `entry-line-number`：两条路径都必须保留凭证行号。
- Affected code:
  - `frontend/src/pages/AccountingMode/Step1SelectType.tsx`
  - `frontend/src/pages/AccountingMode/Step2ImportSource.tsx`
  - `frontend/src/pages/AccountingMode/Step3GenerateEntries.tsx`
  - 新增或改造人工录入凭证页面/组件
  - `frontend/src/api/client.ts`
  - 后端可复用现有 `commit-entries` / `AccountingEntry` 落库结构，必要时新增人工凭证提交 API

## ADDED Requirements

### Requirement: 凭证输入模式选择

The system SHALL allow the user to choose between AI intelligent voucher generation and traditional manual voucher entry in 财务总账 / 凭证管理 Step1.

#### Scenario: 用户选择 AI 智能生成

- **WHEN** 用户在 Step1 选择「根据原始资料 AI 智能生成凭证」
- **THEN** 系统进入原始资料上传流程
- **AND** 后续由系统识别资料类型并生成会计凭证草稿

#### Scenario: 用户选择人工录入

- **WHEN** 用户在 Step1 选择「传统人工录入凭证」
- **THEN** 系统进入人工凭证录入流程
- **AND** 用户可以手工填写凭证日期、凭证字号、摘要、科目、借贷金额、对方单位等信息

### Requirement: 两条路径统一产出标准会计凭证

The system SHALL ensure both input paths produce the same standard accounting voucher structure.

#### Scenario: AI 路径生成标准凭证

- **WHEN** AI 根据原始资料生成凭证草稿并经用户复核确认
- **THEN** 系统落库为统一的标准会计凭证分录
- **AND** 后续可用于总账、明细账、试算平衡、财务报表、审计分析和导出

#### Scenario: 人工路径生成标准凭证

- **WHEN** 用户手工录入凭证并提交
- **THEN** 系统落库为同一套标准会计凭证分录
- **AND** 后续处理方式与 AI 生成凭证完全一致

### Requirement: 标准凭证基本字段

The system SHALL require standard voucher fields before voucher confirmation.

#### Scenario: 标准凭证字段完整

- **WHEN** 用户确认凭证
- **THEN** 每张凭证至少包含凭证日期、凭证号或凭证字、摘要、科目代码/名称、借方金额、贷方金额、行号
- **AND** 借贷金额必须平衡
- **AND** 金额精度保留 2 位小数

### Requirement: 保留输入来源标识

The system SHALL keep an input source marker for traceability without splitting voucher models.

#### Scenario: 凭证追溯来源

- **WHEN** 凭证由 AI 生成
- **THEN** 系统记录该凭证来源为 `ai_generated`
- **AND** 可追溯到原始资料或导入任务

#### Scenario: 凭证追溯人工录入

- **WHEN** 凭证由人工录入
- **THEN** 系统记录该凭证来源为 `manual_entry`
- **AND** 该凭证仍使用统一标准凭证结构

## MODIFIED Requirements

### Requirement: 凭证管理 Step1 语义

Step1 SHALL no longer be primarily described as selecting source document types. It SHALL be described as selecting voucher input mode.

### Requirement: 原始资料类型选择

原始资料类型选择 SHALL move into the AI 智能生成路径 and serve as auxiliary information for AI identification. It SHALL not replace the voucher input mode decision.

### Requirement: 凭证复核流程

Step4 SHALL review standard voucher drafts regardless of whether they come from AI generation or manual entry.

## REMOVED Requirements

无。
