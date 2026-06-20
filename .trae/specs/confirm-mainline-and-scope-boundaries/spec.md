# 主线任务与需求边界确认 Spec

## Why

项目已经连续完成多项需求，当前工作区中同时存在凭证、审计、UI、导航、基础资料、首次登录、Agent、报表等多条线索。如果不重新确认主线任务和需求边界，后续容易把 UI 优化、导航修正、业务流程建设、测试环境修复混在一起，导致需求重叠、实现范围扩大和验收口径不清。

本 spec 的目标是回顾当前上下文，确认当前主线任务、支线任务和明确的非目标，确保下一步只处理一个边界清楚的任务。

## What Changes

- 回顾当前已完成的核心上下文。
- 确认当前主线任务：**UI / 导航一致性收口与用户体验低风险优化**。
- 标记当前主线内的直接冲突点：左侧导航顺序中“管理中心位置”需要回到用户明确指定口径。
- 标记当前阻断项：Trae 终端环境异常导致 `pytest` / `npm run lint` 暂时无法可靠运行。
- 明确哪些需求不属于当前主线，避免与凭证、审计、银行、税务、固定资产、进销存真实业务建设重叠。
- 明确下一步执行目标必须是小范围、低风险、可验收的 UI / 导航收口，不新增大业务功能。

## Impact

- Affected specs:
  - `review-ui-consistency-and-ux`：已完成 UI/UX 评审，建议下一步做低风险 UI 文案与占位状态一致性优化。
  - `reorder-main-navigation-modules`：已执行导航调整，但文档/实现中出现“管理中心位置”与用户原始口径不一致的风险，需要优先校正。
  - `review-context-and-fix-next-blocker`：已修复人工录入基础资料加载 500，后续仍需在终端恢复后补跑完整测试。
  - `audit-day-book-import`：仍是后续状态一致性目标，但不应混入当前 UI 主线。
- Affected code:
  - 当前 spec 阶段不直接修改代码。
  - 后续如进入执行，预计只涉及：
    - `frontend/src/layout/MainShell.tsx`
    - `frontend/src/App.tsx`
    - 少量 UI 文案 / 占位页文件

## ADDED Requirements

### Requirement: 上下文确认

The system SHALL summarize the current project context before choosing the next task.

#### Scenario: 回顾上下文

- **WHEN** 进入本轮主线确认
- **THEN** 系统 SHALL 确认项目当前已完成 AI/人工凭证统一输入、AI 证据充分性、EntryTag 语义增强、人工凭证 UI、首次登录上下文、UI 评审和导航顺序调整等需求
- **AND** 系统 SHALL 识别当前仍存在测试终端异常和部分 spec 状态不一致问题

### Requirement: 主线任务确认

The system SHALL identify one active mainline task.

#### Scenario: 确认当前主线

- **WHEN** 用户要求确认主线任务
- **THEN** 当前主线 SHALL 被确认为：UI / 导航一致性收口与用户体验低风险优化
- **AND** 当前主线 SHALL 只处理界面顺序、导航层级、提示文案、占位状态、技术术语外露等低风险事项
- **AND** 当前主线 SHALL NOT 新增凭证、审计、银行、税务、固定资产、进销存的真实业务功能

### Requirement: 导航顺序边界

The system SHALL preserve the user-specified sidebar order without reinterpretation.

#### Scenario: 左侧导航顺序确认

- **WHEN** 校验导航顺序
- **THEN** 左侧一级导航 SHALL 按用户原始口径确认：Agent 助手、财务总账、审计系统、银行模块、税务模块、固定资产模块、进销存模块、基础资料、管理中心、自定义模块
- **AND** 工作台 MAY 保留为系统首页入口，位于最前面
- **AND** 管理中心 SHALL 位于基础资料之后、自定义模块之前
- **AND** 自定义模块 SHALL 位于最底部

### Requirement: 非目标边界

The system SHALL explicitly avoid overlapping unrelated requirements.

#### Scenario: 当前主线执行时

- **WHEN** 执行当前主线
- **THEN** 不 SHALL 同时处理：
  - 凭证确认 / 复核 / 过账流程重构
  - 审计序时簿导入完整补齐
  - 银行真实对账流程
  - 税务真实申报流程
  - 固定资产真实折旧流程
  - 进销存真实库存与成本流程
  - Agent 模型能力增强
  - 权限体系重构
  - 数据库迁移大改

### Requirement: 测试边界

The system SHALL distinguish code failure from terminal environment failure.

#### Scenario: 自动化测试无法运行

- **WHEN** `python --version`、`node --version`、`pytest` 或 `npm run lint` 在 Trae 终端中无日志直接 exit code 1
- **THEN** 系统 SHALL 标记为终端环境异常
- **AND** 不 SHALL 将其误判为项目代码测试失败
- **AND** 在终端恢复前 SHALL 使用 IDE 诊断作为辅助检查，但不得替代最终自动化测试

### Requirement: 下一步目标决策

The system SHALL choose the next execution target inside the confirmed mainline.

#### Scenario: 决策下一步

- **WHEN** 本轮主线确认完成
- **THEN** 推荐下一步 SHALL 是：校正并收口左侧导航顺序与文档口径，使其严格符合用户原始指定顺序
- **AND** 该任务 SHALL 只修改导航顺序、导航高亮、相关 spec 状态，不扩展其他模块功能
- **AND** 后续再单独进入“低风险 UI 文案与占位状态一致性优化”

## MODIFIED Requirements

### Requirement: 当前执行优先级

当前执行优先级 SHALL 调整为：

1. 先确认主线与边界。
2. 再校正 `reorder-main-navigation-modules` 中管理中心位置与用户口径不一致的问题。
3. 终端环境恢复后补跑前端 lint / TypeScript 和必要后端测试。
4. 再进入低风险 UI 文案与占位状态一致性优化。
5. 最后另行处理 `audit-day-book-import` 状态一致性或业务补齐。

## REMOVED Requirements

无。
