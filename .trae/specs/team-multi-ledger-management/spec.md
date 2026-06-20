# 团队多账套管理与授权隔离 Spec

## Why

当前系统所有数据存储在单一数据库中，团队之间只有逻辑隔离（通过 team_id 字段），没有真正的"账套"概念。财务实务中，一个事务所（团队）通常服务多个客户，每个客户有独立的账套（物理隔离的数据源）。用户（会计师）通过授权访问特定账套，项目跟着账套走，便于留痕定责。默认账套应为用户最后工作的账套，便于项目跟进。

## What Changes

- 新增账套（Ledger）模型：团队下的独立数据源容器
- 新增用户-账套授权模型：控制用户可访问哪些账套
- 所有业务表增加 `ledger_id` 字段：实现逻辑隔离
- 新增账套管理 API：创建、切换、授权、归档
- 前端首页增加账套选择器：登录后先选账套，再进入工作台
- 默认账套机制：记录用户最后使用的账套，下次登录自动进入
- 项目归属账套：所有凭证、审计项目、期间等业务数据归属账套

## Impact

- Affected specs:
  - `user-auth-system`
  - `team-dashboard-and-module-workspaces`
  - `enterprise-module-ia-and-daybook-flow`
  - `accounting-period-snapshot`
  - `internal-accounting-unit`
- Affected code:
  - `backend/app/models/team.py` — 增加账套关系
  - `backend/app/models/user.py` — 增加默认账套、授权关系
  - `backend/app/models/` — 新增 ledger.py, user_ledger_auth.py
  - `backend/app/models/` — 所有业务表增加 ledger_id
  - `backend/app/services/` — 新增 ledger_service.py
  - `backend/app/api/` — 新增 routes_ledger.py
  - `frontend/src/pages/WorkspacePage.tsx` — 增加账套选择器
  - `frontend/src/stores/authStore.ts` — 增加当前账套状态

## ADDED Requirements

### Requirement: 账套模型

系统 SHALL 提供账套（Ledger）模型，作为团队下的独立数据源容器。

#### Scenario: 创建账套
- **WHEN** 团队管理员创建新账套
- **THEN** 系统生成账套记录，包含名称、所属团队、状态
- **AND** 可选配置数据库隔离方式（当前逻辑隔离，预留物理隔离字段）

#### Scenario: 账套字段
- **THEN** 账套包含：id, name, team_id, status(active/archived/frozen), database_url(预留), created_at, updated_at

### Requirement: 用户-账套授权

系统 SHALL 通过授权模型控制用户可访问哪些账套，不是自由切换。

#### Scenario: 授权访问
- **WHEN** 用户被授权访问账套 A
- **THEN** 用户可在账套 A 中查看和操作数据
- **AND** 未授权的账套 B 数据不可见

#### Scenario: 授权字段
- **THEN** 授权模型包含：user_id, ledger_id, role(owner/admin/viewer), granted_at, granted_by

### Requirement: 业务数据归属账套

系统 SHALL 让所有业务数据（凭证、分录、期间、审计项目等）归属账套。

#### Scenario: 凭证归属
- **WHEN** 在账套 A 中创建凭证
- **THEN** 凭证记录包含 ledger_id = A
- **AND** 查询时自动过滤当前账套

#### Scenario: 跨账套隔离
- **WHEN** 用户切换到账套 B
- **THEN** 看不到账套 A 的凭证
- **AND** 数据物理上在同一数据库但逻辑隔离

### Requirement: 默认账套机制

系统 SHALL 记录用户最后使用的账套，下次登录自动进入。

#### Scenario: 记录最后账套
- **WHEN** 用户切换账套或执行操作
- **THEN** 系统记录 user's last_ledger_id

#### Scenario: 自动进入默认账套
- **WHEN** 用户下次登录
- **THEN** 系统自动进入 last_ledger_id 对应的账套
- **AND** 如果默认账套已失效，提示用户选择

### Requirement: 前端账套选择器

系统 SHALL 在首页/工作台提供账套选择器。

#### Scenario: 登录后选择账套
- **WHEN** 用户登录后进入首页
- **THEN** 如果用户有多个授权账套，显示账套选择器
- **AND** 如果只有一个账套，自动进入

#### Scenario: 账套切换
- **WHEN** 用户在工作台点击切换账套
- **THEN** 弹出选择器，列出所有授权账套
- **AND** 切换后页面数据刷新

### Requirement: 项目留痕与定责

系统 SHALL 确保所有操作记录包含账套、用户、时间，便于跟踪定责。

#### Scenario: 操作日志
- **WHEN** 用户在账套中执行关键操作（结账、反结账、损益结转）
- **THEN** 审计日志包含：ledger_id, user_id, action, timestamp

## MODIFIED Requirements

### Requirement: 首页大盘

原首页大盘展示团队级汇总，修改为展示**当前账套**的汇总数据。
- 增加账套选择器在顶部
- 切换账套后大盘数据刷新
- 保留团队名称显示

### Requirement: 用户模型

原 User 模型增加：
- `last_ledger_id` — 默认账套
- `ledger_auths` — 授权关系

### Requirement: 所有业务表

所有业务表（AccountingEntry, AccountingPeriod, PeriodSnapshot, ImportJob, AuditTest 等）增加 `ledger_id` 字段。

## REMOVED Requirements

无。

## 财务视角说明

- **账套 = 客户的独立账簿**：一个事务所服务多个客户，每个客户一套账，物理隔离防止串账。
- **授权 = 审计项目的权限控制**：不是每个会计师都能看所有客户的账，而是根据项目分配权限。
- **项目跟着账套走**：审计项目 "2026年报审计" 绑定到 "客户甲账套"，所有凭证、测试、报告都在这个账套内，便于留痕定责。
- **默认账套 = 工作连续性**：会计师昨天在客户甲账套工作，今天登录直接继续，不需要重新选择。
- **当前阶段逻辑隔离**：所有数据在同一数据库，通过 ledger_id 过滤。后续可升级为物理隔离（每个账套独立数据库文件）。
