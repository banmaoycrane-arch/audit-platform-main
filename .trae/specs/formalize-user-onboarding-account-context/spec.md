# 首次登录引导与用户账套关系正式化 Spec

## Why

当前首次登录引导并不完全是 mock：它已经调用真实的团队、账套 API 创建数据；但它仍存在明显的临时逻辑和占位内容，例如短信验证码为开发模拟、用户协议/隐私政策为占位文本、注册后只根据团队/账套数量简单跳转。更关键的是，用户注册后与历史账号资料、团队、账套、项目、会计主体、已导入数据之间的关系没有被正式建模，后续容易造成数据归属不清、权限不清、项目延续困难。

本 spec 的目标是把“注册用户进入系统后到底属于哪个团队、哪个账套、哪个项目、哪些历史数据”的关系正式定义清楚，避免系统继续依赖临时判断，降低后续开发和用户使用风险。

## What Changes

- 明确当前首次登录引导的真实与 mock 边界。
- 新增“用户上下文状态”概念，用于判断用户是否已完成团队、账套、项目、会计主体绑定。
- 注册/登录后不再仅凭 `teams.length === 0 || ledgers.length === 0` 判断是否进入 onboarding。
- 引导流程从“创建团队 → 创建账套”升级为“确认身份 → 选择/创建团队 → 选择/创建账套 → 选择/创建项目 → 绑定或确认会计主体 → 进入工作台”。
- 支持用户认领或关联历史资料，例如已有账号、已有团队授权、历史账套、已导入凭证、项目资料。
- 对未完成匹配的用户赋予临时工作状态，允许进入系统但明确提示“尚未绑定正式团队/账套/项目”。
- 明确不同开发阶段的难度和边界，优先实现最小闭环，避免一开始做过重的企业级身份治理。

## Impact

- Affected specs:
  - `user-auth-system`：注册、登录、验证码、用户信息。
  - `team-multi-ledger-management`：团队、账套、授权、当前账套。
  - `ledger-register-project-concept-unification`：项目、账套、成员关系。
  - `team-dashboard-and-module-workspaces`：登录后工作台入口。
  - `confirm-context-and-next-target`：首次登录临时角色过渡需求。
- Affected code:
  - `frontend/src/pages/OnboardingPage.tsx`
  - `frontend/src/pages/Auth/LoginPage.tsx`
  - `frontend/src/pages/Auth/RegisterPage.tsx`
  - `frontend/src/stores/authStore.tsx`
  - `frontend/src/api/client.ts`
  - `backend/app/api/routes_auth.py`
  - `backend/app/services/auth_service.py`
  - `backend/app/api/routes_team.py`
  - `backend/app/api/routes_ledger.py`
  - `backend/app/api/routes_project.py`
  - `backend/app/services/ledger_management_service.py`

## ADDED Requirements

### Requirement: 明确 mock 与真实边界

The system SHALL clearly distinguish development mock behavior from production onboarding behavior.

#### Scenario: 当前首次登录引导说明

- **WHEN** 系统检查首次登录引导实现
- **THEN** 应确认团队和账套创建使用真实后端 API
- **AND** 应确认短信验证码、用户协议、隐私政策等仍存在开发占位或模拟内容
- **AND** 应在代码和 UI 中避免把占位内容伪装成正式生产能力

### Requirement: 用户上下文状态

The system SHALL provide a user context status after registration or login.

#### Scenario: 用户已完成上下文绑定

- **WHEN** 用户登录后已经有团队、账套、项目和当前账套授权
- **THEN** 系统 SHALL 直接进入工作台
- **AND** 当前团队、账套、项目状态 SHALL 可被前端读取

#### Scenario: 用户未完成上下文绑定

- **WHEN** 用户登录后缺少团队、账套、项目或会计主体绑定
- **THEN** 系统 SHALL 返回明确的 onboarding status
- **AND** 前端 SHALL 根据缺失项进入对应引导步骤

### Requirement: 注册后关系正式化

The system SHALL define the relationship between registered user, teams, ledgers, projects, accounting entities and historical data.

#### Scenario: 新用户无历史资料

- **WHEN** 新用户注册且没有历史团队/账套/项目授权
- **THEN** 系统 SHALL 引导用户创建或加入团队
- **AND** 再创建或选择账套和项目

#### Scenario: 用户存在历史资料

- **WHEN** 用户手机号、用户名或受邀授权可以匹配历史团队/账套/项目
- **THEN** 系统 SHALL 展示可认领或可加入的历史资料
- **AND** 用户确认后 SHALL 建立正式授权关系

### Requirement: 临时工作状态

The system SHALL allow a temporary onboarding state for users who have not yet matched a team, ledger or project.

#### Scenario: 临时进入系统

- **WHEN** 用户已注册但尚未完成团队/账套/项目匹配
- **THEN** 系统 MAY 允许进入受限工作台
- **AND** 用户角色 SHALL 标识为 temporary 或 onboarding_pending
- **AND** 系统 SHALL 明确提示该状态下数据只是临时工作区，需绑定正式团队/账套/项目后才能归档为正式资料

### Requirement: 历史资料归属确认

The system SHALL prevent historical account data from being silently attached to the wrong user or ledger.

#### Scenario: 历史数据待确认

- **WHEN** 系统发现已有导入任务、凭证、项目或账套可能属于当前用户
- **THEN** 系统 SHALL 将其列为“待确认历史资料”
- **AND** 用户或管理员确认前，不 SHALL 自动并入正式账套

### Requirement: 开发难度透明化

The system SHALL expose implementation stages for onboarding and account-context governance.

#### Scenario: 分阶段开发

- **WHEN** 规划首次登录引导正式化
- **THEN** 系统 SHALL 按阶段实现：
  1. 最小闭环：返回用户上下文状态，修正跳转逻辑；
  2. 关系闭环：团队/账套/项目/会计主体绑定；
  3. 历史资料认领：手机号、邀请、历史导入数据匹配；
  4. 权限治理：临时角色、管理员确认、审计日志。

## MODIFIED Requirements

### Requirement: 注册/登录后的跳转逻辑

注册/登录后 SHALL 不再仅根据团队列表或账套列表长度决定跳转。系统 SHALL 调用用户上下文接口，由后端明确返回：是否需要 onboarding、缺失哪些绑定、推荐下一步动作。

### Requirement: 首次登录引导流程

首次登录引导 SHALL 从简单创建团队/账套页面，升级为根据用户上下文状态动态展示的引导流程。每一步都应说明其财务含义，例如团队表示权限协作范围，账套表示核算数据范围，项目表示具体工作承载对象，会计主体表示核算边界。

### Requirement: 开发模拟内容

开发模拟内容 SHALL 明确标记为开发环境能力，不作为正式业务规则。例如短信验证码开发返回、协议文本占位，都需要与正式用户关系治理分开处理。

## REMOVED Requirements

无。
