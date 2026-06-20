# 凭证复核与确认入账流程语义收口 Spec

## Why

当前财务总账凭证流程中，Step3、Step4、Step5 对“草稿、复核、确认、落库、入账、导出”的表达不够统一，容易让会计用户误解为“还没复核就已经正式入账”或“已经入账后又回头复核”。

本 spec 目标是低风险收口凭证主流程语义，让 AI 生成和人工录入都清晰落在同一条业务路径：草稿凭证 → 复核调整 → 确认入账 / 导出。

## What Changes

- 回顾当前上下文与角色分工，确认本任务只处理凭证主流程语义。
- 统一会计模式 Step3、Step4、Step5 的标题、按钮、提示语和空状态。
- 将 Step3 表达为“生成 / 形成待复核凭证草稿”，避免直接表达为最终入账。
- 将 Step4 表达为“复核调整凭证草稿”，明确这是正式确认前的审核环节。
- 将 Step5 表达为“确认入账与导出”，明确最终确认发生在复核之后。
- 保留现有 `AccountingEntry` 数据结构与现有接口，不建设复杂审批流或正式总账过账引擎。

## Impact

- Affected specs:
  - `unify-voucher-input-modes`：已有 AI / 人工输入统一产物，本 spec 补齐后续流程语义。
  - `accounting-step4-real-review`：已有 Step4 真实分录复核，本 spec 优化复核位置和文案口径。
  - `export-accounting-package`：Step5 仍保留导出，本 spec 增加“确认入账”业务语义。
- Affected code:
  - `frontend/src/pages/AccountingMode/Step3GenerateEntries.tsx`
  - `frontend/src/pages/AccountingMode/Step4ReviewEntries.tsx`
  - `frontend/src/pages/AccountingMode/Step5Export.tsx`
  - 必要时同步 `FlowNav` 上下文文案，不改后端接口。

## ADDED Requirements

### Requirement: 凭证主流程语义

The system SHALL present accounting voucher flow as draft generation, review adjustment, then final confirmation and export.

#### Scenario: 用户查看会计模式步骤

- **WHEN** 用户进入财务总账凭证流程
- **THEN** 系统 SHALL 清晰表达流程为：生成或录入草稿凭证 → 复核调整 → 确认入账 / 导出
- **AND** 系统 SHALL 避免在复核前使用“正式入账”“最终确认”“过账完成”等最终状态文案

### Requirement: Step3 形成待复核凭证草稿

The system SHALL describe Step3 output as voucher drafts awaiting review.

#### Scenario: AI 生成凭证

- **WHEN** 用户在 Step3 生成 AI 凭证
- **THEN** 页面 SHALL 表达其结果为“待复核凭证草稿”
- **AND** 提交按钮 SHALL 表达为“保存草稿并进入复核”或等价文案

#### Scenario: 人工录入凭证

- **WHEN** 用户通过人工录入形成凭证
- **THEN** 页面 SHALL 表达其结果为“人工录入的待复核凭证草稿”
- **AND** 不 SHALL 暗示绕过复核直接完成正式入账

### Requirement: Step4 复核调整草稿凭证

The system SHALL make Step4 the review and adjustment stage before final confirmation.

#### Scenario: 用户复核分录

- **WHEN** 用户进入 Step4
- **THEN** 页面 SHALL 明确当前对象为“待复核凭证草稿”
- **AND** 页面 SHALL 允许用户理解该环节用于检查摘要、科目、金额、往来单位和借贷平衡
- **AND** 下一步按钮 SHALL 表达为进入“确认入账 / 导出”

### Requirement: Step5 确认入账与导出

The system SHALL present Step5 as the final user-facing confirmation point before export.

#### Scenario: 用户完成复核后进入 Step5

- **WHEN** 用户进入 Step5
- **THEN** 页面 SHALL 明确说明凭证已完成复核，可进行确认入账和导出
- **AND** 导出格式选择 SHALL 保持现有能力不变
- **AND** 不 SHALL 新增复杂审批流、账簿过账引擎或后端数据模型重构

## MODIFIED Requirements

### Requirement: 统一输入模式后续流程

AI 生成和人工录入两条路径 SHALL 在用户可见流程上统一进入“待复核凭证草稿 → 复核调整 → 确认入账 / 导出”，不再使用会让用户误解为两套凭证生命周期的文案。

### Requirement: Step4 真实复核语义

Step4 SHALL continue loading真实分录，但在用户界面中 SHALL 被解释为正式确认前的复核调整环节，而不是已完成入账后的附加检查。

## REMOVED Requirements

无。
