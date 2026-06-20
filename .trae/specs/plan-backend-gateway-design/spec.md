# 后端网关设计规划 Spec

## Why
当前后端已经有较多业务路由，统一挂载在 FastAPI 入口中，但还没有明确的“后端网关层”规划。随着系统进入团队、账套、记账、审计、AI 生成、报表、文件导入等多模块阶段，需要先确认网关的业务目标和边界，再决定是否实施。

从财务系统视角看，后端网关相当于“所有业务单据和请求进入系统前的统一收发岗”：它不负责具体记账、审计判断，但负责确认谁在访问、访问哪个账套、是否有权限、请求是否可追踪、异常是否可审计。

## What Changes
- 仅做规划确认，不立即改业务代码。
- 明确后端网关的定位：统一入口、认证鉴权、账套上下文、请求追踪、错误格式、安全边界、审计日志入口。
- 明确当前代码现状：`backend/app/main.py` 直接挂载所有路由，已有 CORS、认证、JWT 密钥强制配置，但认证/账套权限/错误处理还没有统一网关化。
- 明确分阶段目标：先做轻量 FastAPI 内部网关层，再根据部署需要考虑 Nginx/反向代理/API Gateway。
- 输出下一步可执行实施范围，供用户确认后再开发。

## Impact
- Affected specs: 用户认证、团队/账套管理、生命周期日志、导入、凭证、审计、报表、AI Agent
- Affected code: `backend/app/main.py`, `backend/app/core/dependencies.py`, `backend/app/core/security.py`, 未来可能新增 `backend/app/core/middleware.py` 或 `backend/app/core/gateway.py`

## ADDED Requirements
### Requirement: 网关定位
系统 SHALL 将后端网关定义为业务 API 的统一入口治理层，而不是替代具体业务服务。

#### Scenario: 用户访问任一业务 API
- **WHEN** 用户访问记账、审计、基础资料、报表或 AI 接口
- **THEN** 网关层应先处理通用事项
- **AND** 业务路由只处理本模块业务逻辑

### Requirement: 认证与公开接口边界
系统 SHALL 明确公开接口和受保护接口。

#### Scenario: 公开接口
- **WHEN** 用户访问注册、登录、健康检查
- **THEN** 系统允许未登录访问

#### Scenario: 业务接口
- **WHEN** 用户访问账套、凭证、审计、报表、文件、AI 相关接口
- **THEN** 系统应要求有效用户身份
- **AND** 不应由每个业务文件分散决定安全策略

### Requirement: 账套上下文
系统 SHALL 在网关或统一依赖层识别当前团队、账套、期间上下文。

#### Scenario: 多账套访问
- **WHEN** 用户访问某个账套下的业务数据
- **THEN** 系统应确认用户属于该团队或拥有该账套权限
- **AND** 防止 A 企业用户读取 B 企业账套数据

### Requirement: 请求追踪与审计留痕
系统 SHALL 为关键请求提供 request_id，并为关键财务动作保留审计日志入口。

#### Scenario: 发生错误或用户反馈问题
- **WHEN** 某次导入、结账、反结账、AI 转人工或审计报告生成出现异常
- **THEN** 系统可通过 request_id 追踪本次请求
- **AND** 关键业务动作应进入生命周期或审计日志

### Requirement: 统一错误格式
系统 SHALL 使用统一错误响应格式，便于前端展示和用户理解。

#### Scenario: 后端拒绝请求
- **WHEN** 权限不足、账套不匹配、资料不足、参数错误或系统异常发生
- **THEN** 前端应收到稳定格式的错误信息
- **AND** 错误信息应包含业务可理解说明

### Requirement: 基础安全策略
系统 SHALL 在网关规划中覆盖 CORS、JWT 密钥、请求大小、文件上传类型、频率限制和敏感信息隐藏。

#### Scenario: 外部请求进入系统
- **WHEN** 请求来自浏览器、脚本或第三方工具
- **THEN** 系统应限制不安全来源和不合理请求
- **AND** 不应向前端暴露数据库连接串、密钥或内部堆栈

## MODIFIED Requirements
### Requirement: 后端入口职责
`backend/app/main.py` SHALL 逐步从“直接集中注册所有路由”调整为“应用装配入口”，通用网关能力通过中间件或统一依赖层承载，业务路由保持清晰。

## REMOVED Requirements
无。
