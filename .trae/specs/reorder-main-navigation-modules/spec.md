# 主导航模块顺序与自定义模块预留 Spec

## Why

当前左侧导航顺序与用户期望的业务模块认知顺序不一致，管理中心位置过前，自定义模块也需要稳定地预留在最底部。

本 spec 目标仅限于统一左侧主导航的一级模块顺序，让系统入口更符合财务审计产品的使用路径，并在底部预留自定义模块区域。登录异常、工作台数据加载、后端接口问题不纳入本规格。

## What Changes

- 调整 `MainShell` 左侧一级导航顺序为：
  1. 工作台
  2. Agent 助手
  3. 财务总账
  4. 审计系统
  5. 银行模块
  6. 税务模块
  7. 固定资产模块
  8. 进销存模块
  9. 基础资料
  10. 管理中心
  11. 自定义模块
- 自定义模块固定预留在左侧导航最下面。
- 管理中心位于基础资料之后、自定义模块之前。
- 固定资产模块和进销存模块从单一路由入口调整为可展开模块，保持与银行/税务等模块风格一致。
- 自定义模块保留可配置/可扩展的导航区域，可承载更细层级的模块入口，例如风险列表、凭证列表、专项分析、客户自定义流程等。
- 保持现有路由可访问，不破坏已注册页面。

## Impact

- Affected specs:
  - `saas-shell-and-navigation`：主导航结构。
  - `team-dashboard-and-module-workspaces`：模块工作台入口。
  - `review-ui-consistency-and-ux`：低风险 UI 一致性优化目标。
  - `workspace-navigation-continuity`：导航连续性和高亮。
- Affected code:
  - `frontend/src/layout/MainShell.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/pages/Workspaces/FixedAssetsWorkspace.tsx`
  - `frontend/src/pages/Workspaces/InventoryWorkspace.tsx`
  - `frontend/src/pages/PlaceholderModulePage.tsx`

## ADDED Requirements

### Requirement: 主导航顺序

The system SHALL render the main sidebar navigation in the business order specified by the user.

#### Scenario: 用户查看左侧导航

- **WHEN** 用户进入系统内任意页面
- **THEN** 左侧一级导航 SHALL 按以下顺序展示：工作台、Agent 助手、财务总账、审计系统、银行模块、税务模块、固定资产模块、进销存模块、基础资料、管理中心、自定义模块
- **AND** 自定义模块 SHALL 位于最底部

### Requirement: 固定资产与进销存模块层级化

The system SHALL present fixed assets and inventory as first-level business modules.

#### Scenario: 用户查看固定资产和进销存

- **WHEN** 用户查看左侧导航
- **THEN** 固定资产模块 SHALL 作为一级模块展示
- **AND** 进销存模块 SHALL 作为一级模块展示
- **AND** 两者 MAY 包含工作台和后续业务子入口

### Requirement: 管理中心后置

The system SHALL place management center after business and master data modules.

#### Scenario: 用户查看管理中心

- **WHEN** 用户查看左侧导航
- **THEN** 管理中心 SHALL 位于基础资料之后、自定义模块之前
- **AND** 管理中心 SHALL 继续包含团队管理、账簿管理、账簿文件、项目管理等管理类入口

### Requirement: 自定义模块预留

The system SHALL reserve a bottom navigation group for custom modules.

#### Scenario: 展示自定义模块

- **WHEN** 系统存在更具体层级或客户自定义入口
- **THEN** 这些入口 MAY 放入自定义模块分组
- **AND** 自定义模块 SHALL 固定在导航底部
- **AND** 现阶段 SHALL 至少保留凭证列表、风险列表、工作台等示例或常用入口

### Requirement: 导航高亮与父级点击

The system SHALL keep menu selection and parent module navigation consistent after reordering.

#### Scenario: 用户点击一级模块

- **WHEN** 用户点击财务总账、审计系统、银行模块、税务模块、固定资产模块、进销存模块或基础资料
- **THEN** 系统 SHALL 默认进入对应模块工作台或主入口
- **AND** 当前页面 SHALL 正确高亮对应菜单项

## MODIFIED Requirements

### Requirement: MainShell 导航结构

`MainShell` 的 `navItems` SHALL 按新的业务模块顺序组织，管理中心 SHALL 位于基础资料之后、自定义模块之前，自定义模块 SHALL 固定放在最底部。

### Requirement: 自定义模块说明

自定义模块 SHALL 被视为“可扩展入口区域”，用于承载更具体层级、客户自定义、专项分析或临时前置展示的模块入口，而不是系统主业务模块本身。

## REMOVED Requirements

无。
