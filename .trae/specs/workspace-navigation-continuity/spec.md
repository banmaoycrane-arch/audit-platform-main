# 工作台页面导航连贯性 Spec

## Why

当前页面虽然可通过 URL 访问，但测试页面之间缺少统一工作台导航关系，导致用户需要手动复制地址，业务流程不连贯。财务软件应像 ERP 一样提供稳定的主菜单、流程入口和步骤间跳转，让记账、审计、基础资料、期间结账、报表之间形成可操作闭环。

## What Changes

- 将记账模式与审计模式步骤页纳入统一 `MainShell` 工作台布局，而不是作为孤立全屏页面。
- 优化左侧导航菜单层级：
  - 工作台
  - Agent 助手
  - 记账模式（Step 1-5）
  - 审计模式（Step 1-6）
  - 凭证管理
  - 基础资料
  - 会计期间
  - 报表
  - 风险列表
- 在向导步骤页顶部/底部增加“返回工作台 / 上一步 / 下一步 / 查看相关模块”导航。
- 在工作台首页增加常用测试入口卡片。
- 修复菜单选中态，让 `/accounting/step/x`、`/audit/step/x` 能正确高亮对应菜单。
- 不改变后端 API，不改变现有 URL。

## Impact

- Affected specs:
  - `saas-shell-and-navigation`
  - `summary-library`
  - `dashboard-home-and-day-book-import`
- Affected code:
  - `frontend/src/App.tsx`
  - `frontend/src/layout/MainShell.tsx`
  - `frontend/src/pages/HomePage.tsx`
  - `frontend/src/pages/WorkspacePage.tsx`
  - `frontend/src/pages/AccountingMode/*`
  - `frontend/src/pages/AuditMode/*`

## ADDED Requirements

### Requirement: 统一工作台 Shell

系统 SHALL 让主要测试页面在统一工作台 Shell 内展示，使用户始终能看到侧边栏导航和顶部栏。

#### Scenario: 打开记账步骤页
- **WHEN** 用户访问 `/accounting/step/3`
- **THEN** 页面显示在工作台 Shell 内
- **AND** 左侧菜单可见
- **AND** 记账模式菜单高亮

#### Scenario: 打开审计步骤页
- **WHEN** 用户访问 `/audit/step/6`
- **THEN** 页面显示在工作台 Shell 内
- **AND** 左侧菜单可见
- **AND** 审计模式菜单高亮

### Requirement: 侧边栏流程导航

系统 SHALL 在侧边栏中展示记账模式 Step 1-5 与审计模式 Step 1-6 的子菜单。

#### Scenario: 从侧边栏进入审计报告导出
- **WHEN** 用户点击“审计模式 / Step 6 导出报告”
- **THEN** 系统跳转到 `/audit/step/6`

### Requirement: 页面内流程按钮

系统 SHALL 在记账和审计步骤页提供清晰的上一步、下一步、返回工作台操作。

#### Scenario: 从记账 Step 3 进入 Step 4
- **WHEN** 用户完成 Step 3 并点击下一步
- **THEN** 系统跳转到 `/accounting/step/4`，并尽量保留 `jobId`、`periodId` 等查询参数

### Requirement: 工作台测试入口

系统 SHALL 在工作台首页提供常用测试入口卡片，便于用户从业务场景进入页面。

#### Scenario: 用户进入工作台
- **WHEN** 用户访问 `/workspace`
- **THEN** 可看到记账流程、审计流程、基础资料、期间结账、报表、Agent 助手等入口

## MODIFIED Requirements

### Requirement: SAAS Shell 导航

现有 Shell 不仅覆盖基础页面，还 SHALL 覆盖记账与审计向导页面，避免主流程页面与工作台割裂。

## REMOVED Requirements

无。

## 财务视角说明

- 记账流程、审计流程、基础资料、期间结账、报表之间应形成类似财务软件主菜单的闭环。
- 对会计测试来说，最重要的是“当前做到账务流程哪一步”清楚可见；对审计测试来说，最重要的是“证据导入、分录导入、执行测试、复核发现、导出报告”之间可连续跳转。
- 本需求只改前端导航与页面连贯性，不调整账务数据逻辑。