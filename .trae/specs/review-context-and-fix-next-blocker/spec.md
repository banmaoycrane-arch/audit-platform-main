# 当前上下文复盘与下一步阻断问题修复 Spec

## Why

项目已经连续完成多项关键需求：AI/人工凭证统一输入、AI 证据充分性、EntryTag 语义体系、手工凭证录入 UI、首次登录用户上下文正式化等。当前需要重新确认角色、代码库、工作区需求状态，并选择下一步最有价值且最不冲突的执行目标。

从用户最新反馈看，“加载人工录入基础资料失败：Internal Server Error”是当前直接影响手工凭证录入流程的阻断问题。它优先级高于继续扩展新功能，因为基础资料加载失败会导致凭证日期、期间、科目、往来单位等控件无法正常工作。

## What Changes

- 回顾并确认当前项目角色分工。
- 回顾当前代码库结构、前后端核心模块和最近完成的需求。
- 汇总工作区 specs 中的已完成、未完成、状态不一致需求。
- 明确当前最优先执行目标：修复“加载人工录入基础资料失败：Internal Server Error”。
- 将后续次级目标列为：核验 `audit-day-book-import` 状态不一致问题。
- 本 spec 通过后，优先进入阻断问题诊断与修复，不新增大功能。

## Impact

- Affected specs:
  - `improve-manual-voucher-entry-ui`：手工凭证录入 UI 已完成，但基础资料加载出现运行时错误。
  - `formalize-user-onboarding-account-context`：用户上下文已正式化，可能影响带权限/账簿的基础资料加载。
  - `add-ledger-files-customer-context-coa-presets`：会计科目、往来单位、账簿文件等基础资料能力已完成。
  - `audit-day-book-import`：仍存在 tasks/checklist 未勾选，属于次级状态一致性目标。
- Affected code:
  - `frontend/src/pages/AccountingMode/Step2ImportSource.tsx`
  - `frontend/src/api/client.ts`
  - `backend/app/api/routes_coa.py`
  - `backend/app/api/routes_counterparties.py`
  - `backend/app/api/routes_accounting_periods.py`
  - `backend/app/api/routes_entry_generation.py`
  - `backend/app/core/dependencies.py`
  - 相关后端测试与前端 TypeScript 检查

## ADDED Requirements

### Requirement: 确认角色与协作方式

The system SHALL preserve the agreed collaboration roles.

#### Scenario: 角色确认

- **WHEN** 执行本次上下文复盘
- **THEN** 用户 SHALL 被视为专业会计师、编程初学者、项目决策者
- **AND** AI SHALL 作为技术实现者、编程知识补充者、财务视角翻译者
- **AND** 后续决策 SHALL 以财务逻辑正确性优先

### Requirement: 确认代码库现状

The system SHALL identify the current codebase structure before choosing the next execution target.

#### Scenario: 代码库确认

- **WHEN** 读取当前代码库
- **THEN** 系统 SHALL 确认后端为 FastAPI + SQLAlchemy + SQLite/PostgreSQL + Qdrant 相关服务
- **AND** 前端为 React + TypeScript + Vite + Ant Design
- **AND** 当前核心能力包括用户认证、团队/账簿/项目、凭证导入、手工凭证、AI 生成、EntryTag、基础资料、报表、审计、风险识别

### Requirement: 确认工作区需求状态

The system SHALL summarize completed, incomplete, and inconsistent requirements from workspace specs.

#### Scenario: 已完成需求确认

- **WHEN** 检查工作区 specs
- **THEN** 系统 SHALL 确认近期已完成：
  - AI 与人工凭证统一输入路径
  - AI 证据充分性与 draft 暂存
  - EntryTag 语义体系增强
  - 主科目、对方单位与重分类规则
  - 手工凭证录入 UI 优化
  - 首次登录用户上下文正式化
  - 账簿文件、客户上下文、行业预设科目

#### Scenario: 未完成或状态不一致需求确认

- **WHEN** 检查未勾选任务
- **THEN** 系统 SHALL 识别 `audit-day-book-import` 仍存在 tasks/checklist 未勾选
- **AND** 系统 SHALL 识别 progress/entity 相关 checklist 中存在环境或大样本验证类未完成项
- **AND** 系统 SHALL 将这些作为后续状态一致性或非阻断验证项

### Requirement: 优先修复人工录入基础资料加载错误

The system SHALL prioritize fixing the manual voucher base data loading Internal Server Error.

#### Scenario: 用户进入人工凭证录入

- **WHEN** 用户进入 Step2 人工凭证录入界面
- **THEN** 系统 SHALL 成功加载基础资料
- **AND** 基础资料 SHALL 至少包括会计期间、会计科目、往来单位或其可用子集
- **AND** 不 SHALL 显示 Internal Server Error

#### Scenario: 后端基础资料接口异常

- **WHEN** 基础资料接口发生错误
- **THEN** 后端 SHALL 返回可理解的业务错误或明确的技术边界说明
- **AND** 前端 SHALL 显示具体失败来源，例如“会计科目加载失败”或“会计期间加载失败”

### Requirement: 不与其他任务冲突

The system SHALL avoid starting unrelated feature work while fixing the blocker.

#### Scenario: 阻断问题修复阶段

- **WHEN** 执行下一步目标
- **THEN** 系统 SHALL 只诊断和修复人工录入基础资料加载相关代码
- **AND** 不 SHALL 同时重构审计序时簿、报表或权限体系

## MODIFIED Requirements

### Requirement: 下一步执行顺序

下一步执行顺序 SHALL 调整为：

1. 优先修复“加载人工录入基础资料失败：Internal Server Error”。
2. 运行后端相关测试与前端 TypeScript 检查。
3. 修复完成后，再核验 `audit-day-book-import` 的实际代码与 tasks/checklist 状态。
4. 之后再进入新的业务功能扩展。

## REMOVED Requirements

无。
