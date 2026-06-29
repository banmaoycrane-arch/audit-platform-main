# 注册与后端可用性回归修复 Spec

## Why

用户反馈 `/login` 的注册失败，同时 `http://127.0.0.1:8000/` 出现 `ERR_CONNECTION_REFUSED`。这说明系统入口仍不稳定：如果后端服务未运行或注册后没有正确进入 onboarding，用户无法完成“注册 → 团队 → 账簿 → 工作台”的最小业务闭环。

## What Changes

- 修复注册成功后的前端跳转逻辑，与登录保持一致：有团队/账簿进入工作台，无团队/账簿进入 onboarding
- 增加后端根路径健康响应，访问 `http://127.0.0.1:8000/` 时能明确看到服务已启动
- 增加或确认本地服务启动方式，保证前端和后端可同时访问
- 补充注册回归测试，覆盖注册、获取当前用户、注册后初始化路径

## Impact

- Affected specs:
  - `user-auth-system`
  - `fix-login-regression`
  - `team-ledger-management-ui`
- Affected code:
  - `backend/app/main.py`
  - `backend/app/api/routes_auth.py`
  - `frontend/src/pages/Auth/RegisterPage.tsx`
  - `frontend/src/api/client.ts`
  - `backend/tests/test_auth_api.py`

## ADDED Requirements

### Requirement: 后端根路径可识别服务状态

系统 SHALL 在后端根路径提供最小健康响应，便于用户判断后端是否启动。

#### Scenario: 访问后端根路径
- **WHEN** 用户访问 `http://127.0.0.1:8000/`
- **THEN** 系统返回服务名称和运行状态
- **AND** 不应出现连接拒绝或空白页面

### Requirement: 注册后进入初始化闭环

系统 SHALL 在注册成功后进入与登录相同的初始化判断流程。

#### Scenario: 新用户注册成功但无团队/账簿
- **WHEN** 用户完成注册
- **THEN** 系统保存 Token 并获取当前用户信息
- **AND** 如果用户没有团队或账簿，跳转 `/onboarding`

#### Scenario: 用户已有团队和账簿
- **WHEN** 用户注册或登录后已经具备团队和账簿
- **THEN** 系统进入 `/workspace`

### Requirement: 注册失败原因可识别

系统 SHALL 在注册失败时提供可理解的错误提示。

#### Scenario: 后端不可用
- **WHEN** 前端请求注册接口但后端不可用
- **THEN** 前端显示网络/服务不可用相关提示，而不是误导性的业务错误

## MODIFIED Requirements

### Requirement: RegisterPage 注册流程

注册页面 SHALL 复用登录后的用户、团队、账簿初始化逻辑，避免注册成功后直接进入无上下文的工作台。

## REMOVED Requirements

无。

## 财务视角说明

注册是新会计人员进入系统的第一步。注册成功后不能直接进入没有团队、没有账簿的空工作台，而应当进入 onboarding，完成团队和账簿初始化。后端根路径健康响应类似“系统是否开机”的检查入口，便于非技术用户判断服务状态。
