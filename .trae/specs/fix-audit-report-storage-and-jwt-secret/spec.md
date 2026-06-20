# 审计报告存储与 JWT 密钥安全修复 Spec

## Why
审计报告属于审计成果数据，不能依赖进程内全局变量保存，否则多用户、多线程或多进程场景下会发生数据混淆、丢失或内存持续增长。JWT 密钥不能在代码中保留默认开发密钥，否则生产环境漏配时令牌可被伪造。

## What Changes
- 验证 `_audit_reports: dict[int, dict] = {}` 是否被接口读写并是否存在跨请求共享风险。
- 将审计报告从进程内全局变量改为数据库持久化存储，并与导入任务 ID 关联。
- 保持现有审计报告生成和查询接口行为可用。
- 验证 `dev-secret-key-do-not-use-in-production` 是否仍会作为 JWT 默认密钥使用。
- 移除 JWT 默认硬编码密钥，改为强制读取配置中的 `secret_key`。
- 缺少 `secret_key` 时，认证相关能力应明确失败，避免静默使用弱密钥。

## Impact
- Affected specs: 审计测试、审计报告、用户认证、安全配置
- Affected code: `backend/app/api/routes_audit_tests.py`、审计报告模型/服务、`backend/app/core/security.py`、配置和相关测试

## ADDED Requirements
### Requirement: 审计报告持久化存储
系统 SHALL 将审计报告保存到数据库，并通过导入任务 ID 关联报告记录。

#### Scenario: 生成审计报告
- **WHEN** 用户对导入任务生成审计报告
- **THEN** 系统将报告内容保存到数据库
- **AND** 报告记录包含导入任务 ID

#### Scenario: 查询审计报告
- **WHEN** 用户查询指定导入任务的审计报告
- **THEN** 系统从数据库读取该导入任务对应报告
- **AND** 不依赖进程内全局变量

### Requirement: 移除审计报告全局变量
系统 SHALL 不再使用模块级可变字典保存审计报告。

#### Scenario: 多请求访问审计报告
- **WHEN** 多个请求生成或读取不同导入任务的审计报告
- **THEN** 报告数据按导入任务隔离
- **AND** 不因共享全局字典导致数据串扰

### Requirement: JWT 密钥强制配置
系统 SHALL 从配置读取 JWT 密钥，且不得保留默认开发密钥作为回退值。

#### Scenario: 已配置密钥
- **WHEN** `secret_key` 已配置
- **THEN** 系统使用该密钥签发和解析 JWT

#### Scenario: 未配置密钥
- **WHEN** `secret_key` 未配置或为空
- **THEN** 系统抛出明确配置错误
- **AND** 不签发或解析 JWT

## MODIFIED Requirements
### Requirement: 登录和令牌认证
登录、注册和令牌解析逻辑 SHALL 依赖显式配置的 JWT 密钥。开发环境也必须通过配置提供密钥，不允许代码内默认密钥兜底。

## REMOVED Requirements
### Requirement: 进程内审计报告缓存
**Reason**: 进程内全局变量会导致多用户数据串扰、多进程不一致和内存不可控增长。
**Migration**: 改为数据库持久化记录，并通过导入任务 ID 查询。

### Requirement: JWT 默认开发密钥
**Reason**: 默认密钥会在生产漏配时形成可伪造 JWT 的安全风险。
**Migration**: 通过 `.env` 或运行环境变量提供 `secret_key`。
