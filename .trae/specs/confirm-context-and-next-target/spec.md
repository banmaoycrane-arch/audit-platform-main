# 回顾上下文与下一步执行目标确认 Spec

## Why

项目已经经历多轮功能实现，当前需要重新确认代码库现状、双方角色分工、已完成与未完成需求，以及下一步最合理的执行目标，避免重复开发或与既有任务冲突。

本次确认的核心目的不是新增业务功能，而是建立一个清晰的执行基线：先确认已经完成什么，再确认仍然缺什么，最后确定下一步优先做什么。

## What Changes

- 复盘当前代码库结构与技术栈。
- 确认用户与 AI 助手的角色边界。
- 汇总当前已完成的核心需求。
- 汇总当前已提出但尚未正式实施的新需求。
- 识别存在状态不一致的 spec，例如代码可能已实现但 checklist 未勾选。
- 给出下一步推荐执行目标。
- 不修改业务代码。
- 不新增业务功能。

## Impact

- Affected specs:
  - `unify-voucher-input-modes`：已完成，确认为当前记账路径基线。
  - `audit-day-book-import`：存在 checklist 未勾选状态，需要优先核验是否已经完成并补齐状态。
  - `auto-generate-entries-from-source`：下一步 AI 生成规则将继续基于该能力扩展。
  - `entry-tag-vector-sync`：EntryTag 的业务语义需要进一步强化。
  - `user-auth-system` / `team-multi-ledger-management`：首次登录临时角色与团队/账套匹配相关。
- Affected code:
  - 本 spec 本身不要求修改业务代码。
  - 后续目标可能影响：`entry_generation_service.py`、`Step2ImportSource.tsx`、`Step3GenerateEntries.tsx`、`EntryTag` 相关服务、登录/团队初始化流程。

## ADDED Requirements

### Requirement: 确认代码库上下文

The system SHALL provide a current-state confirmation of the project structure and main implemented capabilities.

#### Scenario: 确认当前代码库

- **WHEN** 执行本次上下文复盘
- **THEN** 确认项目是前后端分离架构
- **AND** 后端为 FastAPI + SQLAlchemy + SQLite/PostgreSQL + Qdrant
- **AND** 前端为 React + TypeScript + Vite + Ant Design
- **AND** 当前核心模块包括财务总账、凭证管理、报表、审计、风险识别、团队/账套/项目管理

### Requirement: 确认角色边界

The system SHALL preserve the agreed collaboration roles.

#### Scenario: 用户与 AI 分工明确

- **WHEN** 后续继续开发
- **THEN** 用户作为专业会计师、编程初学者、项目决策者提出财务需求并验收财务逻辑
- **AND** AI 作为技术实现者、编程知识补充者、财务视角翻译者，将财务需求转化为可运行代码

### Requirement: 确认已完成需求

The system SHALL identify completed requirements to avoid duplicate implementation.

#### Scenario: 已完成能力确认

- **WHEN** 回顾当前 specs
- **THEN** 确认 `unify-voucher-input-modes` 已完成
- **AND** 确认凭证管理已形成 AI 智能生成与人工录入两条输入路径
- **AND** 确认两条路径最终统一落入标准会计凭证结构

### Requirement: 确认新增待办需求池

The system SHALL capture newly raised requirements as candidate next specs.

#### Scenario: 识别待办需求

- **WHEN** 汇总用户最新补充
- **THEN** 识别以下待办方向：
  - AI 生成凭证前的原始资料充分性规则与 draft 暂存机制
  - EntryTag 作为二级科目、辅助核算、摘要和业务语义统一标签体系
  - 主科目、对方单位、往来重分类与余额方向由正负决定的会计理解
  - 首次登录未匹配团队/主体/项目时的临时角色过渡机制

### Requirement: 确认下一步执行目标

The system SHALL recommend one next execution target based on dependency and financial logic priority.

#### Scenario: 推荐下一步

- **WHEN** 当前上下文复盘完成
- **THEN** 推荐下一步优先执行「AI 生成凭证的原始资料充分性规则与 draft 暂存机制」
- **AND** 在正式实现该目标前，先核验并补齐 `audit-day-book-import` 的任务勾选状态，避免遗留状态干扰

## MODIFIED Requirements

### Requirement: 下一步开发顺序

后续开发 SHALL 先处理状态一致性，再进入新业务逻辑：
1. 核验 `audit-day-book-import` 实际代码与测试状态，并补齐 tasks/checklist。
2. 新建立并实施「AI 原始资料充分性规则与 draft 暂存」spec。
3. 再进入 EntryTag 语义体系增强。
4. 再处理首次登录临时角色与团队/账套/项目匹配。

## REMOVED Requirements

无。
