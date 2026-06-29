# SAAS Shell 与导航 Spec

## Why

当前前端只有"两个引导式向导"（记账模式 / 审计模式），缺少 SAAS 后台标配的左侧主导航 + 顶栏 + 嵌套路由 + Tab 工作区，与目标产品（参见达普记账截图）信息架构差距大。同时已有的多个后端 API（CoA、Counterparty、Period 等）在 UI 上无入口，导致用户感知不到能力。

## What Changes

- 引入 `MainShell` 布局：顶栏（账簿切换/搜索/帮助/用户）+ 左侧主导航（折叠）+ 中间内容区
- 路由分层：`MainShell` 作为外层 Layout 路由，子模块嵌套
- 主导航条目（最小集合，骨架页占位）：
  - 工作台（首页占位）
  - 凭证管理（链接到现有 `EntriesPage`）
  - 基础资料（CoA / Counterparty）
  - 会计期间
  - 审计模式入口
  - 记账模式入口
- 不引入 React Query / Zustand，本期保持现有 useState；下一期再迁移

## Impact

- 新增：`frontend/src/layout/MainShell.tsx`、`frontend/src/layout/SideNav.tsx`、`frontend/src/layout/TopBar.tsx`
- 修改：`frontend/src/App.tsx`（嵌套路由）

## ADDED Requirements

### Requirement: 主 Shell 布局

系统 SHALL 提供 `MainShell`，包含顶栏 + 左侧主导航 + 内容 Outlet。

#### Scenario: 路由切换不刷新 Shell
- **WHEN** 用户从 `/entries` 切换到 `/coa`
- **THEN** Shell 不卸载，仅内容区切换

### Requirement: 左侧主导航

系统 SHALL 在左侧导航中暴露：工作台、凭证管理、基础资料（科目、对方单位）、会计期间、记账模式、审计模式。

## MODIFIED Requirements

### Requirement: 顶级路由

非首页内容均在 `MainShell` 之下，`/`、`/accounting/*`、`/audit/*` 三个原向导路由保留兼容。

## REMOVED Requirements

无。
