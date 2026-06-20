# 注册失败多维度诊断 Spec

## Why

用户在注册页面看到“注册失败，请检查网络或稍后重试”，同时怀疑可能是后端服务没有启动。`ERR_CONNECTION_REFUSED` 的最常见原因就是目标端口没有服务监听，因此需要先区分“服务未启动/端口不可用”和“注册业务逻辑失败”。当前前端把不同错误统一显示为通用提示，导致无法准确定位问题。

## What Changes

- 将“后端服务是否启动”作为注册失败诊断的第一步
- 对注册流程进行多维度诊断：后端服务、前端代理、注册接口、数据库重复约束、注册后初始化链路、错误提示映射
- 将“注册接口失败”和“注册成功后初始化失败”拆开处理
- 增强前端错误提示，让用户看到明确原因
- 补充后端和前端回归验证，确保注册后能进入 onboarding 或工作台

## Impact

- Affected specs:
  - `user-auth-system`
  - `fix-register-and-backend-availability`
  - `team-ledger-management-ui`
- Affected code:
  - `frontend/src/pages/Auth/RegisterPage.tsx`
  - `frontend/src/api/client.ts`
  - `backend/app/api/routes_auth.py`
  - `backend/tests/test_auth_api.py`

## ADDED Requirements

### Requirement: 服务可用性优先诊断

系统 SHALL 在判断注册失败前，优先确认后端服务是否可访问。

#### Scenario: 后端未启动
- **WHEN** 用户访问 `http://127.0.0.1:8000/` 或前端请求 `/api/auth/register` 时连接被拒绝
- **THEN** 系统应提示“后端服务未启动或端口不可访问”
- **AND** 不应误判为账号、密码、协议或手机号问题

#### Scenario: 后端已启动
- **WHEN** `GET /` 和 `GET /health` 均返回 200
- **THEN** 注册失败应继续检查请求参数、账号重复、手机号重复和初始化流程

### Requirement: 注册失败原因可区分

系统 SHALL 区分注册失败的真实原因，而不是统一显示“请检查网络或稍后重试”。

#### Scenario: 前端代理失败
- **WHEN** 后端服务已启动但前端 `/api/*` 请求无法代理
- **THEN** 页面提示“前端代理到后端失败，请检查开发服务配置”

#### Scenario: 用户名或手机号重复
- **WHEN** 后端返回用户名或手机号已存在
- **THEN** 页面提示“用户名已存在”或“手机号已注册”

#### Scenario: 协议未勾选
- **WHEN** 用户未勾选用户协议或隐私政策
- **THEN** 页面提示必须先同意协议

#### Scenario: 注册成功但初始化失败
- **WHEN** 注册接口已经返回 Token，但后续 `me/teams/ledgers` 请求失败
- **THEN** 系统不应提示注册失败
- **AND** 应保留登录状态并引导用户进入 onboarding 或提示初始化失败

### Requirement: 注册链路诊断可验证

系统 SHALL 提供可测试的注册链路。

#### Scenario: 后端注册接口验证
- **WHEN** 测试调用 `POST /api/auth/register`
- **THEN** 返回 Token，并能使用 Token 调用 `/api/auth/me`

#### Scenario: 前端注册页验证
- **WHEN** 用户提交合法注册表单
- **THEN** 注册成功后进入 `/onboarding` 或 `/workspace`

## MODIFIED Requirements

### Requirement: RegisterPage 错误处理

注册页面 SHALL 分离以下阶段：

1. 后端服务可用性检查
2. 注册请求阶段
3. Token 保存阶段
4. 当前用户加载阶段
5. 团队/账套初始化阶段
6. 页面跳转阶段

每个阶段失败时，应显示对应的明确提示。

## REMOVED Requirements

无。

## 财务视角说明

注册是新会计人员进入系统的“开户”动作。开户失败不能只提示“网络错误”，必须先判断“系统是否开机”，也就是后端服务是否启动；再判断账号是否重复、协议是否确认、团队和账套初始化是否完成。这样才能保证后续团队、账套、项目权限链路可追溯、可定位、可修复。
