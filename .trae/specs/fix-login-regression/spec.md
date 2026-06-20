# 登录回归修复 Spec

## Why

用户在 `http://127.0.0.1:5173/login` 测试时，账号密码登录和验证码登录均失败。登录是进入团队、账套、项目管理链路的入口，如果登录失败，后续账套初始化、团队绑定、工作台验收都无法进行。

## What Changes

- 修复前端登录请求与后端服务地址不一致导致的失败风险
- 修复验证码登录前后端返回结构不一致导致的失败风险
- 修复登录成功后初始化团队/账套信息时的异常阻塞风险
- 增加登录回归测试，覆盖账号密码登录、验证码获取、验证码登录、登录后用户信息获取

## Impact

- Affected specs:
  - `user-auth-system`
  - `team-ledger-management-ui`
- Affected code:
  - `frontend/vite.config.ts`
  - `frontend/src/pages/Auth/LoginPage.tsx`
  - `frontend/src/api/client.ts`
  - `backend/app/api/routes_auth.py`
  - `backend/app/services/auth_service.py`
  - `backend/tests/test_auth_api.py`

## ADDED Requirements

### Requirement: 登录入口可用

系统 SHALL 保证登录页的账号密码登录和验证码登录均可在本地开发环境正常使用。

#### Scenario: 账号密码登录成功
- **WHEN** 用户输入已注册账号和正确密码
- **THEN** 系统返回 Token
- **AND** 前端保存 Token 并进入工作台或 onboarding 页面

#### Scenario: 验证码登录成功
- **WHEN** 用户获取验证码并输入正确验证码
- **THEN** 系统返回 Token
- **AND** 前端保存 Token 并进入工作台或 onboarding 页面

### Requirement: 本地服务地址稳定

系统 SHALL 在本地开发时稳定代理到 `127.0.0.1:8000` 后端服务。

#### Scenario: 前端请求后端
- **WHEN** 前端页面运行在 `127.0.0.1:5173`
- **THEN** `/api/*` 请求应正确转发到 `127.0.0.1:8000`

### Requirement: 验证码返回结构兼容

系统 SHALL 让开发环境验证码接口返回前端可用的信息。

#### Scenario: 开发环境获取验证码
- **WHEN** 用户点击获取验证码
- **THEN** 前端应显示可用于测试的验证码
- **AND** 验证码登录应使用同一验证码完成登录

## MODIFIED Requirements

### Requirement: 登录后初始化

登录成功后，前端 SHALL 尝试加载用户、团队和账套信息；团队/账套为空时进入 onboarding，不能把初始化为空误报为登录失败。

## REMOVED Requirements

无。

## 财务视角说明

登录相当于会计信息系统的“权限入口”。只有用户身份确认后，系统才能判断其所属团队、可访问账套和项目权限。当前修复的目标不是扩展权限体系，而是保证用户能稳定进入后续“团队 → 账套 → 项目”的业务链路。
