# 全项目 UI 一致性与用户体验评审 Spec

## Why

当前项目功能增长较快，已经覆盖登录注册、首次引导、工作台、团队/账簿/项目、凭证流程、基础资料、报表、审计、银行、税务、Agent 等多个模块。虽然大部分页面已接入 Ant Design 和统一 Shell，但不同阶段实现的页面在布局、导航、信息层级、控件密度、错误提示和占位页面风格上可能存在不一致。

本 spec 的目标是先系统识别代码库和 UI 现状，评估整个项目界面是否匹配、美观、功能清晰、用户体验良好，并输出下一步可执行的优化目标，而不是立即大规模重构界面。

## What Changes

- 识别当前前端代码库结构、路由、Shell、核心页面和模块页面。
- 对全项目 UI 一致性进行评审，包括布局、导航、视觉层级、控件风格、文案、错误反馈、空状态、加载状态。
- 从财务用户视角评估功能是否好理解、流程是否连贯、关键操作是否容易找到。
- 识别明显不匹配或体验较差的页面和模块。
- 输出 UI/UX 问题清单与优先级。
- 决策下一步是否进入“低风险统一修复”，例如统一页面标题、卡片间距、按钮位置、空状态、错误提示等。
- 本阶段不直接进行大规模 UI 重构。

## Impact

- Affected specs:
  - `saas-shell-and-navigation`：全局 Shell 与导航。
  - `team-dashboard-and-module-workspaces`：团队工作台与模块工作台。
  - `workspace-navigation-continuity`：流程导航连续性。
  - `improve-manual-voucher-entry-ui`：手工凭证录入 UI。
  - `formalize-user-onboarding-account-context`：首次登录引导 UI。
  - `basic-data-pages` / `add-ledger-files-customer-context-coa-presets`：基础资料页面。
- Affected code:
  - `frontend/src/layout/MainShell.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/pages/WorkspacePage.tsx`
  - `frontend/src/pages/OnboardingPage.tsx`
  - `frontend/src/pages/Auth/LoginPage.tsx`
  - `frontend/src/pages/Auth/RegisterPage.tsx`
  - `frontend/src/pages/AccountingMode/*`
  - `frontend/src/pages/AuditMode/*`
  - `frontend/src/pages/BasicData/*`
  - `frontend/src/pages/Workspaces/*`
  - `frontend/src/pages/Reports/*`
  - `frontend/src/pages/PlaceholderModulePage.tsx`

## ADDED Requirements

### Requirement: 代码库 UI 结构识别

The system SHALL identify the frontend UI structure before making UI/UX judgments.

#### Scenario: 识别前端结构

- **WHEN** 执行 UI 评审
- **THEN** 系统 SHALL 确认前端使用 React + TypeScript + Vite + Ant Design
- **AND** SHALL 识别全局 Shell、路由、工作台、步骤页、基础资料页、报表页、审计页、占位模块页
- **AND** SHALL 区分已完成页面、占位页面和半成品页面

### Requirement: UI 一致性评审

The system SHALL evaluate whether pages are visually consistent and professionally aligned.

#### Scenario: 评审页面风格

- **WHEN** 检查核心页面
- **THEN** 系统 SHALL 评估是否统一使用标题层级、卡片布局、按钮风格、表格风格、间距、图标颜色和提示文案
- **AND** SHALL 标记风格明显不一致或视觉负担过重的页面

### Requirement: 导航与流程体验评审

The system SHALL evaluate whether users can understand where they are and what to do next.

#### Scenario: 评审流程导航

- **WHEN** 用户进入工作台、凭证流程、审计流程或基础资料页面
- **THEN** 系统 SHALL 评估侧边栏高亮、页面标题、步骤导航、返回/下一步操作是否清晰
- **AND** SHALL 标记跳转路径混乱、重复入口过多或命名不一致的问题

### Requirement: 财务用户体验评审

The system SHALL evaluate UI from the perspective of accountants, auditors and finance operators.

#### Scenario: 财务人员使用系统

- **WHEN** 财务人员执行登录、建账、录凭证、维护科目、导入序时簿、查看报表等操作
- **THEN** 系统 SHALL 评估页面是否使用财务人员能理解的语言
- **AND** SHALL 评估关键字段、校验提示、错误提示是否具有业务语义
- **AND** SHALL 标记“技术味太重”或“不知道下一步做什么”的页面

### Requirement: 输出 UI/UX 优先级

The system SHALL produce a prioritized UI/UX improvement decision.

#### Scenario: 评审完成后

- **WHEN** UI/UX 评审完成
- **THEN** 系统 SHALL 输出：
  - 当前整体 UI 匹配度结论
  - 体验较好的页面
  - 体验薄弱的页面
  - 低风险可立即优化项
  - 需要单独 spec 的较大优化项
  - 推荐下一步执行目标

## MODIFIED Requirements

### Requirement: 后续 UI 优化顺序

后续 UI 优化 SHALL 先从全局一致性和低风险体验问题开始，例如页面标题、提示文案、空状态、错误提示和导航命名；不 SHALL 在未完成评审前直接重构所有页面。

## REMOVED Requirements

无。
