# 恢复凭证管理多步骤流程 Spec

## Why

用户指出“凭证管理”原本应与审计模式一样具备多个 Step 的流程，但在企业级一级模块重构后，凭证管理被简化成单一凭证列表入口，导致原“选择类型 → 导入凭证 → 生成分录 → 复核分录 → 导出账套”的记账/凭证流程在财务总账模块中不可见。凭证管理是总账系统的核心入口，应恢复为多步骤流程，并保留凭证列表作为其中的管理视图。

## What Changes

- 在“财务总账”下将“凭证管理”改为父级菜单。
- 凭证管理下恢复多步骤流程：
  - Step 1：选择原始资料类型
  - Step 2：导入原始凭证
  - Step 3：AI 生成会计分录
  - Step 4：复核会计分录
  - Step 5：导出账套
  - 凭证列表：查看已生成/已导入的会计分录
- 保留现有 `/accounting/step/1` 到 `/accounting/step/5` 路由。
- 新增或使用财务总账语义路径：
  - `/ledger/vouchers/step/1` 到 `/ledger/vouchers/step/5`
  - `/ledger/entries`
- `/ledger/vouchers/step/*` 可以复用现有记账模式组件，避免重复开发。
- 页面内流程导航需要在财务总账语义路径下保持连贯，并保留 `jobId`、`periodId` 等查询参数。

## Impact

- Affected specs:
  - `workspace-navigation-continuity`
  - `enterprise-module-ia-and-daybook-flow`
  - `summary-library`
  - `auto-generate-entries-from-source`
- Affected code:
  - `frontend/src/layout/MainShell.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/components/FlowNav.tsx`
  - `frontend/src/pages/AccountingMode/*`
  - `frontend/src/pages/WorkspacePage.tsx`

## ADDED Requirements

### Requirement: 凭证管理多步骤菜单

系统 SHALL 在“财务总账 / 凭证管理”下展示 Step 1-5 流程和凭证列表。

#### Scenario: 查看财务总账菜单
- **WHEN** 用户打开左侧菜单“财务总账”
- **THEN** 可看到“凭证管理”父菜单
- **AND** 凭证管理下包含 Step 1-5 和凭证列表

### Requirement: 财务总账语义路径

系统 SHALL 支持 `/ledger/vouchers/step/1` 到 `/ledger/vouchers/step/5` 访问现有凭证流程页面。

#### Scenario: 打开凭证管理 Step 3
- **WHEN** 用户访问 `/ledger/vouchers/step/3`
- **THEN** 系统显示 AI 生成会计分录页面
- **AND** 页面仍在 MainShell 内

### Requirement: 旧路径兼容

系统 SHALL 保留 `/accounting/step/1` 到 `/accounting/step/5`，避免破坏已有链接。

#### Scenario: 打开旧记账路径
- **WHEN** 用户访问 `/accounting/step/4`
- **THEN** 系统仍显示复核会计分录页面

### Requirement: 流程跳转保留参数

系统 SHALL 在凭证管理 Step 之间跳转时保留 `jobId`、`periodId` 等查询参数。

#### Scenario: 从 Step 3 跳转 Step 4
- **WHEN** 当前 URL 为 `/ledger/vouchers/step/3?jobId=1&periodId=2`
- **THEN** 点击下一步进入 `/ledger/vouchers/step/4?jobId=1&periodId=2`

### Requirement: 工作台入口明确

系统 SHALL 在工作台入口卡片中将“财务总账 / 凭证管理”说明为多步骤流程，而不是单页列表。

#### Scenario: 从工作台进入凭证管理
- **WHEN** 用户点击工作台“财务总账”或“凭证管理”入口
- **THEN** 优先进入 `/ledger/vouchers/step/1`

## MODIFIED Requirements

### Requirement: 财务总账模块

原“财务总账 / 凭证管理”单页入口修改为“凭证管理多步骤流程 + 凭证列表”。

## REMOVED Requirements

无。

## 财务视角说明

- 凭证管理不是单纯的分录列表，它是总账核算的起点：原始凭证进入系统后，需要经历导入、识别、生成分录、复核、导出或入账。
- 审计系统有 Step 1-6，凭证管理也应具备 Step 1-5，这样“记账”和“审计”两条主线结构一致，用户更容易理解。
- 凭证列表只是结果视图，不能替代凭证处理流程。