# 生命周期管理 Spec

## Why

会计账簿、业务台账、项目三者有不同的生命周期驱动因素：
- **会计账簿**：跟随客户合作周期，客户开始合作时创建，合作终止时归档
- **业务台账**：跟随各模块使用周期，银行按月、税务按季度、库存按日更新
- **项目**：跟随工作开展与关闭时间，但管理周期可最大化（项目结束后仍可查看历史）

需要定义各对象的生命周期状态、转换规则、归档策略，以及跨生命周期的数据管理。

## What Changes

- 为 Ledger、Project、各模块台账定义生命周期状态机
- 定义状态转换规则（什么条件下可以转换）
- 定义归档策略（数据保留、查询权限、恢复机制）
- 定义生命周期事件（创建、激活、暂停、归档、删除）
- 前端增加生命周期状态展示和操作入口

## Impact

- Affected specs:
  - `team-multi-ledger-management`
  - `ledger-register-project-concept-unification`
- Affected code:
  - `backend/app/models/ledger.py` — 增加生命周期字段
  - `backend/app/models/project.py` — 增加生命周期字段
  - `backend/app/services/` — 新增生命周期管理服务
  - `frontend/src/components/` — 增加生命周期状态展示

## ADDED Requirements

### Requirement: 会计账簿生命周期

系统 SHALL 为会计账簿定义以下生命周期：

#### 状态定义
| 状态 | 说明 | 可转换到 |
|------|------|----------|
| `draft` | 草稿，刚创建，未初始化科目和期初数据 | `active` |
| `active` | 激活，正常使用中 | `suspended`, `archived` |
| `suspended` | 暂停，客户暂时中止合作，数据冻结 | `active`, `archived` |
| `archived` | 归档，合作终止，数据只读 | `active`（恢复） |
| `deleted` | 已删除，逻辑删除，保留审计日志 | 不可恢复 |

#### 生命周期事件
- **创建**：`draft` → 初始化科目 → `active`
- **激活**：`draft` → `active`（完成初始化）
- **暂停**：`active` → `suspended`（客户暂停合作）
- **恢复**：`suspended` → `active`（客户恢复合作）
- **归档**：`active`/`suspended` → `archived`（合作终止）
- **恢复归档**：`archived` → `active`（特殊情况恢复）
- **删除**：`archived` → `deleted`（彻底删除，需超级权限）

#### 归档策略
- 归档后数据只读，不可新增凭证、分录
- 归档后仍可查询、导出、审计
- 归档账簿不占活跃账簿配额（如果有配额限制）
- 归档满 N 年后可转冷存储（压缩、异地备份）

### Requirement: 业务台账生命周期

系统 SHALL 为各模块业务台账定义以下生命周期：

#### 状态定义
| 状态 | 说明 | 驱动因素 |
|------|------|----------|
| `open` | 开放，正常接收数据 | 模块使用周期 |
| `closed` | 已关闭，当期结束 | 周期结束（月/季/年） |
| `locked` | 锁定，已结账不可修改 | 会计期间结账后 |

#### 周期驱动
- **银行台账**：按月周期，`open` → `closed`（月末）→ `open`（下月初）
- **税务台账**：按季度周期，`open` → `closed`（季末）→ `open`（下季初）
- **库存台账**：按日周期，`open` → `closed`（日结）→ `open`（次日）
- **固定资产台账**：按年周期，`open` → `closed`（年末折旧后）→ `open`（下年初）

#### 与会计账簿的关系
- 业务台账的 `locked` 状态由会计账簿的期间结账触发
- 会计账簿 `archived` 时，所有关联台账自动 `locked`

### Requirement: 项目生命周期

系统 SHALL 为项目定义以下生命周期：

#### 状态定义
| 状态 | 说明 | 可转换到 |
|------|------|----------|
| `planning` | 规划中，未正式开始 | `active` |
| `active` | 进行中，正常工作 | `paused`, `completed` |
| `paused` | 暂停，临时中止 | `active`, `completed` |
| `completed` | 已完成，交付结束 | `active`（ reopen ） |
| `cancelled` | 已取消，不再继续 | 不可恢复 |

#### 管理周期最大化
- 项目 `completed` 后，数据保留完整历史
- `completed` 项目仍可查看、导出、审计
- `completed` 项目不可新增工作记录（只读）
- `completed` 项目可 reopen 为 `active`（如发现新问题）
- 项目历史记录永久保留，用于后续审计追踪

#### 与会计账簿的关系
- 项目可关联多个会计账簿（跨年度审计）
- 项目 `completed` 时，关联账簿不自动归档（账簿生命周期独立）
- 项目 `completed` 后，仍可查看关联账簿的历史数据

### Requirement: 生命周期事件日志

系统 SHALL 记录所有生命周期状态转换事件：

#### 日志字段
- `object_type`（ledger/project/register）
- `object_id`
- `from_status`
- `to_status`
- `triggered_by`（用户/系统/定时任务）
- `triggered_at`
- `reason`（转换原因）

#### 查询接口
- `GET /api/lifecycle/logs?object_type=ledger&object_id=1`
- 返回该对象的所有生命周期事件

## MODIFIED Requirements

### Requirement: Ledger 模型

增加字段：
- `status`（draft/active/suspended/archived/deleted）
- `lifecycle_status`（生命周期状态）
- `activated_at`（激活时间）
- `suspended_at`（暂停时间）
- `archived_at`（归档时间）
- `deleted_at`（删除时间）
- `lifecycle_reason`（状态转换原因）

### Requirement: Project 模型

增加字段：
- `status`（planning/active/paused/completed/cancelled）
- `completed_at`（完成时间）
- `cancelled_at`（取消时间）
- `lifecycle_reason`（状态转换原因）

## REMOVED Requirements

无。

## 财务视角说明

- **会计账簿跟随客户周期**：客户是会计账簿的生命周期驱动者。客户开始合作 → 创建账簿；客户暂停 → 账簿暂停；客户终止 → 账簿归档。这符合事务所的实际业务节奏。
- **业务台账跟随模块周期**：银行按月、税务按季、库存按日。台账的关闭和开启由模块自身决定，不受会计账簿直接影响（但会计结账会锁定台账）。
- **项目管理周期最大化**：审计项目完成后，所有工作底稿、审计证据、沟通记录必须永久保留。这是审计准则的要求（审计底稿保存期限通常为 10 年以上）。项目可以 reopen，因为后续发现重大问题需要追加审计程序。
- **为什么区分生命周期**：三者的驱动因素不同，混在一起会导致状态管理混乱。比如客户暂停合作（账簿 suspended），但税务模块仍在做季度申报（台账 active），同时审计项目已完成（project completed）。三者独立管理，互不影响。
