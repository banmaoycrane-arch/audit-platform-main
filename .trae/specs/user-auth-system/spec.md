# 用户认证与登录系统 Spec

## Why

当前系统没有任何用户认证机制，任何人都可以直接访问工作台和财务数据。作为一个财务系统，必须区分用户身份、控制访问权限，并满足合规要求（用户协议、隐私政策确认）。

## What Changes

- 新增用户模型与认证服务（后端）
- 新增登录/注册页面（前端）
- 支持两种登录方式：账号密码登录、验证码登录
- 用户注册流程包含用户协议与隐私政策确认
- 登录成功后跳转到工作台首页
- 未登录用户访问任何页面自动重定向到登录页
- 预留小程序登录接口扩展点

## Impact

- Affected specs:
  - `saas-shell-and-navigation`
  - `workspace-navigation-continuity`
  - `enterprise-module-ia-and-daybook-flow`
- Affected code:
  - `backend/app/models/` — 新增 User 模型
  - `backend/app/services/` — 新增 auth_service.py
  - `backend/app/api/` — 新增 routes_auth.py
  - `backend/app/core/security.py` — 密码哈希、JWT
  - `frontend/src/pages/Auth/` — 登录、注册页面
  - `frontend/src/App.tsx` — 路由守卫
  - `frontend/src/api/client.ts` — 认证相关 API

## ADDED Requirements

### Requirement: 用户模型

系统 SHALL 提供用户数据模型，包含必要字段。

#### Scenario: 用户注册
- **WHEN** 用户提交注册信息
- **THEN** 系统创建用户记录，密码加密存储

### Requirement: 账号密码登录

系统 SHALL 支持用户名/手机号 + 密码登录。

#### Scenario: 正确密码登录
- **WHEN** 用户输入正确账号密码
- **THEN** 返回 JWT Token，前端保存并跳转工作台

#### Scenario: 错误密码登录
- **WHEN** 用户输入错误密码
- **THEN** 返回 401，不泄露用户是否存在

### Requirement: 验证码登录

系统 SHALL 支持手机号 + 验证码登录（模拟实现，不接入真实短信平台）。

#### Scenario: 验证码登录
- **WHEN** 用户输入手机号和验证码
- **THEN** 如果验证码匹配，返回 JWT Token
- **AND** 如果用户不存在，自动创建用户

#### Scenario: 验证码获取
- **WHEN** 用户点击获取验证码
- **THEN** 系统生成验证码并显示（开发环境）或发送短信（生产环境预留）

### Requirement: 用户协议与隐私政策

系统 SHALL 在注册流程中要求用户同意用户协议和隐私政策。

#### Scenario: 未同意协议
- **WHEN** 用户未勾选同意协议
- **THEN** 注册按钮禁用，提示必须同意

#### Scenario: 查看协议内容
- **WHEN** 用户点击协议链接
- **THEN** 弹出 Modal 展示协议文本

### Requirement: 登录状态管理

系统 SHALL 在前端维护登录状态，未登录用户无法访问内部页面。

#### Scenario: 未登录访问工作台
- **WHEN** 未登录用户访问 `/workspace`
- **THEN** 自动重定向到 `/login`

#### Scenario: Token 过期
- **WHEN** Token 过期或无效
- **THEN** 前端自动清除 Token 并跳转登录页

### Requirement: 路由守卫

系统 SHALL 在路由层面区分公开页面和受保护页面。

#### Scenario: 公开页面
- **WHEN** 用户访问 `/login`、`/register`
- **THEN** 无需登录即可访问

#### Scenario: 受保护页面
- **WHEN** 用户访问 `/workspace`、`/ledger/*`、`/audit/*`
- **THEN** 必须已登录，否则重定向

### Requirement: 小程序登录预留

系统 SHALL 预留小程序登录接口，支持后续扩展。

#### Scenario: 小程序登录
- **WHEN** 小程序调用登录接口
- **THEN** 通过 wx.login 获取 code，后端换取 openid 并创建/关联用户

## MODIFIED Requirements

### Requirement: 首页路由

原 `/` 直接跳转工作台，修改为：
- 已登录：跳转 `/workspace`
- 未登录：跳转 `/login`

## REMOVED Requirements

无。

## 财务视角说明

- 财务系统必须有身份隔离：不同会计主体、不同权限的用户看到的凭证和报表应当不同。
- 用户协议和隐私政策不是形式，而是合规基础：财务数据涉及企业机密，必须明确告知用户数据使用范围。
- 验证码登录比密码登录更适合移动端和小程序场景，但开发环境需要模拟短信发送。
- 当前阶段先实现单用户/单组织，后续再扩展多组织权限模型。