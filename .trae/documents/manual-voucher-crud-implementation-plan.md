# 手工录入并管理凭证功能详细实现方案

> **文档类型**: 功能实现方案（基于项目 /spec 目录中的功能迭代建议）
> **更新日期**: 2026-07-01
> **目标功能**: 实现"手工录入并管理凭证"完整 CRUD 与业务闭环
> **需求来源**: 
> - [improve-manual-voucher-entry-ui spec](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/improve-manual-voucher-entry-ui/spec.md)
> - [unify-voucher-input-modes spec](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/unify-voucher-input-modes/spec.md)
> - [clarify-voucher-review-posting-flow spec](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/clarify-voucher-review-posting-flow/spec.md)
> - [restore-voucher-management-step-flow spec](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/restore-voucher-management-step-flow/spec.md)
> - [accounting-step4-real-review spec](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/accounting-step4-real-review/spec.md)

---

## 1. 功能需求分析

### 1.1 业务场景

本功能面向财务人员，提供传统手工录入凭证的能力，并支持对凭证进行全生命周期管理。主要业务场景包括：

1. **手工录入凭证**：在无法通过 AI 或文件导入生成凭证时，由财务人员手工填写凭证头（日期、凭证字、凭证号、摘要）和分录行（科目、借贷金额、对方单位），提交生成标准会计凭证。
2. **查看凭证**：按账簿、期间、日期、凭证号、摘要、金额等条件查询已录入凭证，查看凭证主表和分录明细。
3. **编辑凭证**：对草稿或已复核但尚未过账的凭证进行修改，包括凭证头信息和分录行内容，系统自动重算借贷平衡。
4. **删除凭证**：对草稿或错误凭证进行整单删除，支持单张删除和批量删除。
5. **复核与入账**：凭证提交后进入复核流程，复核通过后可执行入账（posted）操作，生成总账、明细账等后续数据。
6. **归档与审计追溯**：所有凭证保留来源标识（`manual_entry`）、制单人、制单时间、修改记录，便于审计追溯。

### 1.2 用户角色与权限划分

| 角色 | 功能权限 | 备注 |
|------|----------|------|
| **制单人** | 创建凭证、编辑自己创建的草稿凭证、删除草稿凭证 | 不能复核、入账自己制作的凭证 |
| **复核人** | 查看凭证、复核（verify）凭证、退回草稿 | 遵循不相容职务分离原则 |
| **记账/过账人** | 查看复核通过的凭证、执行入账（post）操作 | 通常由主管会计或指定人员执行 |
| **系统管理员** | 全部操作权限 | 包括取消已入账凭证、修改已结账期间凭证等例外操作 |
| **审计人员** | 只读查看凭证、分录、来源信息 | 用于审计底稿和测试 |

> **权限控制原则**：本阶段只实现基于角色的权限判断，复杂的多人复核权限在后续审计工作流模块中完善。

### 1.3 核心操作流程

#### 1.3.1 凭证创建流程

```
用户进入 财务总账 → 凭证管理 → 手工录入
    ↓
系统自动加载当前账簿、默认打开期间、凭证字建议
    ↓
用户填写凭证头（日期、凭证字、凭证号、摘要、附件数）
    ↓
用户填写分录行（摘要、科目、借方/贷方金额、对方单位）
    ↓
系统实时校验借贷平衡
    ↓
用户选择：保存草稿 / 保存并新增 / 保存并复制 / 提交复核
    ↓
系统后端二次校验 → 创建 Voucher 主表 + AccountingEntry 分录行
    ↓
返回成功信息，跳转凭证列表或继续录入
```

#### 1.3.2 凭证编辑流程

```
用户在凭证列表点击"编辑"
    ↓
系统加载凭证主表和全部分录行到录入表单
    ↓
用户修改凭证头或分录行
    ↓
系统实时校验借贷平衡
    ↓
用户保存
    ↓
系统校验：已结账期间不可修改；已过账凭证不可修改关键字段
    ↓
更新 Voucher 主表 + 删除旧分录行 + 插入新分录行（事务）
    ↓
返回成功信息
```

#### 1.3.3 凭证查询流程

```
用户进入凭证列表页
    ↓
系统默认按当前账簿、当前期间加载凭证列表
    ↓
用户输入筛选条件（凭证号、日期范围、摘要、科目、金额等）
    ↓
系统返回分页结果
    ↓
用户点击"展开"查看分录明细
```

#### 1.3.4 凭证删除流程

```
用户在凭证列表选择单张或多张凭证
    ↓
点击"删除"按钮
    ↓
系统二次确认
    ↓
系统校验：仅允许删除草稿或已取消凭证；已过账凭证需先取消/作废
    ↓
事务删除 Voucher 主表及关联 AccountingEntry 行
    ↓
返回成功信息
```

#### 1.3.5 凭证状态流转

```
┌─────────┐   保存    ┌──────────┐   复核    ┌──────────┐   入账    ┌──────────┐
│  草稿   │ ───────→ │  待复核   │ ───────→ │  已复核   │ ───────→ │  已过账   │
│ draft   │          │ pending  │          │ verified  │          │ posted   │
└─────────┘          └──────────┘          └──────────┘          └──────────┘
     │                    │                    │                    │
     │ 删除               │ 退回               │ 取消               │ 取消过账
     ↓                    ↓                    ↓                    ↓
┌─────────┐          ┌──────────┐          ┌──────────┐          ┌──────────┐
│  已删除  │          │  退回草稿 │          │  已取消   │          │  已取消   │
│ deleted │          │  draft   │          │cancelled │          │cancelled │
└─────────┘          └──────────┘          └──────────┘          └──────────┘
```

> **简化说明**：本阶段状态流转为 `draft → verified → posted`，取消过账作为例外功能（管理员权限）。

---

## 2. 开发步骤规划

### 2.1 需求细化与任务拆解

| 任务编号 | 任务名称 | 说明 | 优先级 |
|----------|----------|------|--------|
| MVE-001 | 需求细化 | 确认字段范围、状态机、权限规则 | P0 |
| MVE-002 | 接口设计 | 输出 RESTful API 设计文档 | P0 |
| MVE-003 | 数据库设计 | 确认是否需要新增字段或索引 | P0 |
| MVE-004 | 后端接口开发 | 实现凭证 CRUD API | P0 |
| MVE-005 | 前端页面开发 | 凭证录入、编辑、列表页面 | P0 |
| MVE-006 | 单元测试 | 后端单元测试，目标覆盖率 ≥ 80% | P0 |
| MVE-007 | 集成测试 | 前后端联调，端到端验证 | P1 |
| MVE-008 | 联调与问题修复 | 修复联调中发现的问题 | P1 |
| MVE-009 | 功能验收与性能优化 | 按验收标准验收，优化响应时间 | P1 |
| MVE-010 | 文档与交付物 | 输出测试报告、用户文档、技术文档 | P1 |

### 2.2 技术方案评审

- 评审点：
  1. 是否复用现有 `voucher_service.py` 服务层能力
  2. 凭证编辑采用"整单替换"还是"分录行级更新"
  3. 凭证状态与 `AccountingEntry` 状态的同步策略
  4. 前端复用 `TraditionalVoucherForm` 还是新建独立页面
- 评审结论：
  1. 复用 `voucher_service.py`，但新增 `/api/vouchers` 独立路由
  2. 凭证编辑采用"整单替换"：删除旧分录，插入新分录，保证事务一致性
  3. Voucher 状态作为凭证主状态，分录状态跟随主状态
  4. 前端复用 `TraditionalVoucherForm`，但新增"编辑模式"加载已有凭证

### 2.3 数据库设计与表结构变更

**变更点**：

1. **Voucher 表**：当前已有完整字段，无需新增列；确保 `organization_id` 非空约束已生效。
2. **AccountingEntry 表**：
   - 确保 `voucher_id` 字段已添加并可建立外键关联（非空约束待评估）
   - 建议新增 `updated_by`、`updated_at` 字段用于审计追踪
   - 建议新增 `version` 字段（可选）用于乐观锁
3. **新增审计日志表（可选）**：
   - `voucher_audit_log`：记录凭证创建、修改、删除、复核、入账等关键操作
4. **索引优化**：
   - 已存在：`ledger_id + voucher_no`
   - 建议新增：`voucher_id`、`ledger_id + voucher_date`、`status`

### 2.4 后端接口开发

详见第 4 节接口设计规范。

### 2.5 前端界面实现

详见第 6 节 UI/UX 设计标准。

### 2.6 测试

- **后端单元测试**：覆盖凭证创建、编辑、删除、查询、借贷平衡校验、期间校验、权限校验
- **集成测试**：从前端页面到后端 API 的完整流程
- **验收测试**：财务验收标准用例（如 1 借 1 贷、多借多贷、不平衡拒绝）

### 2.7 联调与问题修复

- 重点关注金额精度、借贷平衡、期间状态、凭证号唯一性冲突

### 2.8 验收与性能优化

- 验收标准见第 9 节交付物清单
- 性能目标：凭证列表页 < 500ms，单张凭证保存 < 300ms

### 2.9 开发时序

```
第 1 周：MVE-001 ~ MVE-004（后端 API）
第 2 周：MVE-005（前端页面）
第 3 周：MVE-006 ~ MVE-008（测试与联调）
第 4 周：MVE-009 ~ MVE-010（验收与文档）
```

---

## 3. 技术选型

### 3.1 后端技术栈

| 技术 | 选型 | 说明 |
|------|------|------|
| 框架 | FastAPI 0.111+ | 已使用，自带 Pydantic 校验和 OpenAPI 文档 |
| 数据库 | SQLite（默认）/ PostgreSQL（生产） | 开发使用 SQLite，生产可切换 |
| ORM | SQLAlchemy 2.0 | 已使用声明式模型 |
| 迁移 | Alembic | 已纳入依赖 |
| 金额计算 | Python `decimal.Decimal` | 避免浮点误差，金额保留 2 位小数 |
| 认证 | JWT (python-jose + passlib[bcrypt]) | 已使用 Bearer Token 认证 |
| 权限 | 自定义依赖 `get_current_user` / `get_current_ledger` | 已使用 |

### 3.2 前端技术栈

| 技术 | 选型 | 说明 |
|------|------|------|
| 框架 | React 18 + TypeScript 5 | 已使用 |
| 构建工具 | Vite 5 | 已使用 |
| UI 组件库 | Ant Design 6 | 已使用 |
| 日期处理 | dayjs | 已使用 |
| 路由 | react-router-dom 7 | 已使用 |
| 状态管理 | React Context + useState/useCallback | 已使用 `authStore` |
| 表单 | Ant Design Form / 自定义受控表单 | 根据复杂度选择 |

### 3.3 数据存储方案

- **关系型数据库**：存储 Voucher、AccountingEntry、ChartOfAccounts、AccountingPeriod、Counterparty 等结构化数据，保证 ACID 和财务数据一致性。
- **JSON 字段**：用于存储 `original_row` 等半结构化原始数据。
- **向量数据库（Qdrant）**：用于 EntryTag 向量检索，本功能不直接依赖，但需保持兼容。
- **不选择 NoSQL 作为主存储**：财务数据需要强事务、强一致性、复杂查询和审计追溯，关系型数据库更合适。

### 3.4 安全认证与权限控制机制

| 层级 | 机制 | 说明 |
|------|------|------|
| 认证 | JWT Bearer Token | 登录后获取 access token，每次请求携带 `Authorization: Bearer <token>` |
| 账簿隔离 | 请求头 `X-Ledger-Id` 或 `user.last_ledger_id` | 所有凭证操作必须落在指定 `ledger_id` 内 |
| 权限校验 | `user_has_ledger_access` + 角色判断 | 校验用户是否有当前账簿访问权限；复核/入账需特定角色 |
| 期间状态校验 | 已结账期间禁止修改、删除凭证 | 保证会计期间不可篡改 |
| 操作审计 | 操作日志表 + 时间戳/用户ID | 记录凭证创建、修改、删除、复核、入账 |
| 敏感信息 | 数据库密码、JWT 密钥仅存于后端环境变量 | 不暴露到前端 |

---

## 4. 接口设计规范

### 4.1 RESTful API 设计标准

- 资源路径：`/api/vouchers` 作为凭证资源主路径
- HTTP 方法对应 CRUD：
  - `GET /api/vouchers`：查询列表
  - `GET /api/vouchers/{voucher_id}`：查询详情
  - `POST /api/vouchers`：创建凭证
  - `PUT /api/vouchers/{voucher_id}`：更新凭证
  - `DELETE /api/vouchers/{voucher_id}`：删除凭证
  - `POST /api/vouchers/{voucher_id}/verify`：复核凭证
  - `POST /api/vouchers/{voucher_id}/post`：入账凭证
  - `POST /api/vouchers/{voucher_id}/cancel`：取消凭证
- 分页：查询接口使用 `skip`/`limit` 或 `page`/`page_size`
- 排序：默认按 `voucher_date DESC, voucher_no DESC`

### 4.2 请求/响应数据格式定义

#### 4.2.1 创建凭证请求

```json
POST /api/vouchers
{
  "ledger_id": 1,
  "organization_id": 1,
  "voucher_date": "2024-01-15",
  "voucher_type": "记",
  "voucher_number": "001",
  "summary": "支付办公费",
  "attachment_count": 2,
  "period_id": 3,
  "lines": [
    {
      "line_no": 1,
      "summary": "办公费",
      "account_code": "6602",
      "account_name": "管理费用-办公费",
      "debit_amount": "1000.00",
      "credit_amount": "0.00",
      "counterparty": ""
    },
    {
      "line_no": 2,
      "summary": "银行存款",
      "account_code": "1002",
      "account_name": "银行存款",
      "debit_amount": "0.00",
      "credit_amount": "1000.00",
      "counterparty": ""
    }
  ]
}
```

#### 4.2.2 创建凭证响应

```json
{
  "success": true,
  "data": {
    "voucher_id": 123,
    "voucher_no": "记-001",
    "voucher_date": "2024-01-15",
    "status": "draft",
    "total_debit": "1000.00",
    "total_credit": "1000.00",
    "entry_count": 2,
    "created_at": "2024-01-15T10:30:00"
  },
  "message": "凭证创建成功"
}
```

#### 4.2.3 查询凭证列表响应

```json
GET /api/vouchers?ledger_id=1&period_id=3&page=1&page_size=20
{
  "success": true,
  "data": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "voucher_id": 123,
        "voucher_no": "记-001",
        "voucher_date": "2024-01-15",
        "summary": "支付办公费",
        "status": "draft",
        "total_debit": "1000.00",
        "total_credit": "1000.00",
        "entry_count": 2,
        "created_by_name": "张三"
      }
    ]
  }
}
```

#### 4.2.4 凭证详情响应

```json
GET /api/vouchers/123
{
  "success": true,
  "data": {
    "voucher_id": 123,
    "ledger_id": 1,
    "organization_id": 1,
    "voucher_no": "记-001",
    "voucher_date": "2024-01-15",
    "summary": "支付办公费",
    "status": "draft",
    "total_debit": "1000.00",
    "total_credit": "1000.00",
    "attachment_count": 2,
    "created_by": 1,
    "created_by_name": "张三",
    "created_at": "2024-01-15T10:30:00",
    "lines": [
      {
        "entry_id": 1,
        "line_no": 1,
        "summary": "办公费",
        "account_code": "6602",
        "account_name": "管理费用-办公费",
        "debit_amount": "1000.00",
        "credit_amount": "0.00",
        "counterparty": ""
      }
    ]
  }
}
```

### 4.3 错误码与异常处理机制

| 错误码 | 含义 | 触发场景 | 示例 |
|--------|------|----------|------|
| 400 | 请求参数错误 | 借贷不平衡、必填字段缺失、金额格式错误 | "借贷不平衡，差额为 100.00" |
| 403 | 权限不足 | 用户无账簿权限、非管理员操作已结账期间 | "当前用户无此账簿操作权限" |
| 404 | 凭证不存在 | 查询/编辑不存在的 voucher_id | "凭证不存在" |
| 409 | 资源冲突 | 凭证号已存在、凭证已复核/已过账 | "凭证号在当前账簿已存在" |
| 422 | 业务规则校验失败 | 已结账期间禁止修改、已过账凭证不可删除 | "已结账期间禁止修改凭证" |
| 500 | 系统内部错误 | 数据库异常、未知错误 | 需记录日志 |

**异常处理模式**：
- 服务层抛出业务语义异常，如 `VoucherValidationError`、`VoucherBalanceError`、`VoucherStateError`、`VoucherNotFoundError`。
- API 层使用 FastAPI 全局异常处理或路由内 try/except 转换为 `HTTPException`。
- 错误响应必须包含 `message` 字段，中文业务语义明确。

### 4.4 API 文档生成规范

- 使用 FastAPI 自动生成的 OpenAPI/Swagger UI 文档
- 每个接口需包含：
  - 功能摘要（summary）
  - 参数说明（description）
  - 请求/响应 Pydantic Schema
  - 错误响应示例
- 前端 `client.ts` 中的类型定义与后端 Schema 保持一致

---

## 5. 数据处理逻辑

### 5.1 凭证数据结构定义

#### 5.1.1 后端 Pydantic Schema

```python
class VoucherLineCreate(BaseModel):
    line_no: int
    summary: str
    account_code: str
    account_name: str | None = None
    debit_amount: Decimal = Decimal("0.00")
    credit_amount: Decimal = Decimal("0.00")
    counterparty: str | None = None
    counterparty_id: int | None = None

class VoucherCreate(BaseModel):
    ledger_id: int
    organization_id: int
    period_id: int
    voucher_date: date
    voucher_type: str
    voucher_number: str
    summary: str | None = None
    attachment_count: int = 0
    lines: list[VoucherLineCreate]

class VoucherUpdate(BaseModel):
    voucher_date: date | None = None
    voucher_type: str | None = None
    voucher_number: str | None = None
    summary: str | None = None
    attachment_count: int | None = None
    lines: list[VoucherLineCreate] | None = None

class VoucherLineResponse(BaseModel):
    entry_id: int
    line_no: int
    summary: str
    account_code: str
    account_name: str
    debit_amount: Decimal
    credit_amount: Decimal
    counterparty: str | None

class VoucherResponse(BaseModel):
    voucher_id: int
    ledger_id: int
    organization_id: int
    voucher_no: str
    voucher_date: date
    summary: str | None
    status: str
    total_debit: Decimal
    total_credit: Decimal
    attachment_count: int
    created_by: int
    created_by_name: str | None
    created_at: datetime
    lines: list[VoucherLineResponse]
```

#### 5.1.2 前端类型定义

```typescript
interface VoucherLineCreate {
  line_no: number
  summary: string
  account_code: string
  account_name?: string
  debit_amount: string
  credit_amount: string
  counterparty?: string
  counterparty_id?: number
}

interface VoucherCreate {
  ledger_id: number
  organization_id: number
  period_id: number
  voucher_date: string
  voucher_type: string
  voucher_number: string
  summary?: string
  attachment_count: number
  lines: VoucherLineCreate[]
}

interface VoucherUpdate extends Partial<VoucherCreate> {}

interface VoucherLineResponse {
  entry_id: number
  line_no: number
  summary: string
  account_code: string
  account_name: string
  debit_amount: string
  credit_amount: string
  counterparty?: string
}

interface VoucherResponse {
  voucher_id: number
  ledger_id: number
  organization_id: number
  voucher_no: string
  voucher_date: string
  summary?: string
  status: string
  total_debit: string
  total_credit: string
  attachment_count: number
  created_by: number
  created_by_name?: string
  created_at: string
  lines: VoucherLineResponse[]
}
```

### 5.2 数据校验规则

#### 5.2.1 凭证头校验

- `ledger_id`：必填，用户必须拥有该账簿权限
- `organization_id`：必填，必须属于该账簿
- `period_id`：必填，期间必须处于 `open` 或 `reopened` 状态
- `voucher_date`：必填，必须在所选期间范围内
- `voucher_type`：必填，取值在 `['记', '银', '收', '付', '转', '工']` 中
- `voucher_number`：必填，同一账簿内唯一（与 `voucher_type` 组合成 `voucher_no`）
- `summary`：必填或至少有一条分录摘要
- `attachment_count`：非负整数

#### 5.2.2 分录行校验

- 至少存在 2 条有效分录行（1 借 1 贷）
- 每条分录行必须填写摘要、科目代码
- 同一行不能同时有借方金额和贷方金额
- 同一行至少要有借方金额或贷方金额
- 金额必须为非负，保留 2 位小数
- 当科目为往来性质（`1122`, `2203`, `2202`, `1123`, `1221`, `2241` 等）时，对方单位建议必填
- 所有分录行借方合计必须等于贷方合计

#### 5.2.3 状态校验

- 创建时状态为 `draft`
- 只有 `draft` 状态的凭证可以修改、删除
- 只有 `draft` 或 `verified` 状态的凭证可以复核（`verify`）
- 只有 `verified` 状态的凭证可以入账（`post`）
- 已过账凭证不可修改，需先取消过账（管理员权限）
- 已结账期间内凭证不可修改、删除

### 5.3 数据持久化策略

#### 5.3.1 创建凭证

1. 开启数据库事务
2. 校验期间、账簿权限、借贷平衡
3. 生成 `voucher_no = f"{voucher_type}-{voucher_number}"`
4. 插入 `Voucher` 主表记录
5. 插入 `AccountingEntry` 分录行，`voucher_id` 关联主表
6. 提交事务
7. 返回凭证详情

#### 5.3.2 更新凭证

1. 开启数据库事务
2. 查询原凭证，校验存在性和状态（仅 `draft` 可修改）
3. 校验期间、账簿权限、借贷平衡
4. 如果 `voucher_type` 或 `voucher_number` 变化，校验新 `voucher_no` 唯一性
5. 更新 `Voucher` 主表
6. 删除旧的 `AccountingEntry` 分录行
7. 插入新的 `AccountingEntry` 分录行
8. 更新 `updated_by`、`updated_at`（如字段存在）
9. 提交事务
10. 返回凭证详情

#### 5.3.3 删除凭证

1. 开启数据库事务
2. 查询凭证，校验存在性和状态（仅 `draft` 可删除）
3. 校验期间未结账
4. 删除关联 `AccountingEntry` 分录行
5. 删除 `Voucher` 主表记录
6. 提交事务

#### 5.3.4 复核/入账/取消

1. 查询凭证，校验状态流转合法性
2. 校验用户权限
3. 更新 `Voucher.status` 和目标字段（`verified_at`, `posted_at`, `posted_by` 等）
4. 同步更新 `AccountingEntry` 的 `review_status` 和 `post_status`
5. 提交事务

### 5.4 数据关联关系处理

| 主表 | 关联表 | 关系 | 说明 |
|------|--------|------|------|
| Voucher | AccountingEntry | 1:N | 通过 `voucher_id` 关联 |
| Voucher | Ledger | N:1 | 通过 `ledger_id` 关联 |
| Voucher | Organization | N:1 | 通过 `organization_id` 关联 |
| Voucher | AccountingPeriod | N:1 | 通过 `period_id` 关联（逻辑上） |
| Voucher | User | N:1 | 通过 `created_by` / `posted_by` 关联 |
| AccountingEntry | ChartOfAccounts | N:1 | 通过 `account_code` + `ledger_id` 关联（逻辑上） |
| AccountingEntry | Counterparty | N:1 | 通过 `counterparty_id` 关联（可选） |

### 5.5 历史记录与审计日志实现

**方案一（推荐）**：新增 `voucher_audit_log` 表

```sql
CREATE TABLE voucher_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_id INTEGER NOT NULL,
    action VARCHAR(50) NOT NULL, -- create/update/delete/verify/post/cancel
    user_id INTEGER NOT NULL,
    user_name VARCHAR(100),
    old_value JSON,
    new_value JSON,
    action_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(50),
    user_agent TEXT
);
```

**方案二**：在 `Voucher` 表中保留 `created_by`, `created_at`, `updated_by`, `updated_at`, `posted_by`, `posted_at` 等字段，满足基础审计需求。

**本阶段选择**：采用方案二，满足基础审计追溯；方案一作为未来扩展。

---

## 6. UI/UX 设计标准

### 6.1 界面布局与元素规范

#### 6.1.1 凭证录入/编辑页布局

```
┌─────────────────────────────────────────────────────────────────┐
│  页面标题：手工录入凭证 / 编辑凭证                                   │
├─────────────────────────────────────────────────────────────────┤
│  凭证头信息                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ 凭证字   │ │ 凭证号   │ │ 凭证日期 │ │ 会计期间 │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 摘要                                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────┐                                                  │
│  │ 附件数   │                                                  │
│  └──────────┘                                                  │
├─────────────────────────────────────────────────────────────────┤
│  分录明细区域（传统纸面样式）                                     │
│  ┌────┬────────────┬────────┬────────┬────────┬────────┐        │
│  │ 行 │ 摘要       │ 科目   │ 借方   │ 贷方   │ 对方单位│        │
│  ├────┼────────────┼────────┼────────┼────────┼────────┤        │
│  │ 1  │ 办公费     │ 6602   │ 1000.00│        │        │        │
│  │ 2  │ 银行存款   │ 1002   │        │ 1000.00│        │        │
│  └────┴────────────┴────────┴────────┴────────┴────────┘        │
│  [+ 增加分录行]                                                  │
├─────────────────────────────────────────────────────────────────┤
│  借贷平衡提示                                                    │
│  借方合计：1000.00  贷方合计：1000.00  差额：0.00 ✅ 平衡          │
├─────────────────────────────────────────────────────────────────┤
│  [保存草稿] [保存并新增] [保存并复制] [提交复核] [取消]           │
└─────────────────────────────────────────────────────────────────┘
```

#### 6.1.2 凭证列表页布局

```
┌─────────────────────────────────────────────────────────────────┐
│  凭证管理 - 凭证列表                                              │
├─────────────────────────────────────────────────────────────────┤
│  [筛选条件：期间 ▼] [日期范围 ▼] [凭证号 🔍] [摘要 🔍] [科目 🔍] │
│  [状态 ▼] [查询] [重置] [新增凭证] [批量删除]                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 记-001  2024-01-15  支付办公费  借贷平衡 ✅  草稿          │    │
│  │ 制单人：张三   借方：1000.00   贷方：1000.00              │    │
│  │ [展开明细] [编辑] [删除]                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 记-002  2024-01-16  收到货款    借贷平衡 ✅  已复核        │    │
│  │ 制单人：李四   借方：5000.00   贷方：5000.00              │    │
│  │ [展开明细] [查看] [入账] [取消]                            │    │
│  └─────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│  [1] [2] [3] ... [下一页]                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 交互流程设计

#### 6.2.1 录入页交互

- 进入页面时，系统自动填充：
  - 当前账簿的默认打开期间
  - 凭证日期默认当前期间内最近一个工作日或当天
  - 凭证字默认"记"
  - 凭证号建议为当前账簿当前期间最大凭证号 + 1
- 用户选择科目后，自动填充科目名称
- 用户输入金额后，实时计算借贷合计和差额
- 不平衡时，保存按钮禁用，并显示差额提示
- 用户可点击"+ 增加分录行"添加分录行，但保留至少一行
- 用户点击"保存草稿"后，凭证进入列表，状态为 `draft`
- 用户点击"提交复核"后，凭证状态变为 `pending_review` 或 `verified`（根据权限配置）

#### 6.2.2 列表页交互

- 默认展开最近一个月凭证
- 点击"展开明细"显示该凭证的所有分录行
- 草稿状态凭证显示"编辑"和"删除"按钮
- 已复核状态凭证显示"入账"和"取消"按钮
- 批量删除仅对草稿状态凭证生效
- 点击"新增凭证"进入录入页

### 6.3 表单验证与反馈机制

| 验证项 | 触发时机 | 反馈方式 | 提示文案 |
|--------|----------|----------|----------|
| 凭证字必填 | 失焦/提交 | 红色边框 + 提示 | 请选择凭证字 |
| 凭证号必填 | 失焦/提交 | 红色边框 + 提示 | 请输入凭证号 |
| 凭证日期在期间内 | 提交 | 全局提示 | 凭证日期不在所选期间范围内 |
| 至少 2 条分录 | 提交 | 全局提示 | 至少需要一条借方和一条贷方分录 |
| 分录摘要必填 | 失焦/提交 | 红色边框 + 提示 | 请输入摘要 |
| 科目必填 | 失焦/提交 | 红色边框 + 提示 | 请选择科目 |
| 借贷金额不能同时有 | 输入时 | 红色边框 + 提示 | 同一行不能同时存在借方和贷方金额 |
| 借贷平衡 | 实时 | 底部提示 | 借方合计 1000.00，贷方合计 900.00，差额 100.00 |
| 已结账期间 | 提交 | 全局提示 | 当前期间已结账，不能录入凭证 |
| 凭证号重复 | 提交 | 全局提示 | 凭证号在当前账簿已存在 |

### 6.4 响应式设计要求

- 桌面端：完整布局，表单和表格左右留白
- 平板端：表格横向滚动，表头固定
- 移动端：表单字段垂直堆叠，分录行卡片式展示，减少列宽
- 最小支持宽度：768px（桌面端为主），移动端可作为未来优化

### 6.5 视觉风格与品牌一致性

- 使用 Ant Design 6 默认主题色
- 按钮顺序：主按钮在右侧（保存、提交），次按钮在左侧（取消、重置）
- 成功提示使用绿色，错误提示使用红色，警告提示使用黄色
- 凭证纸面样式使用浅灰色背景，模拟真实凭证
- 金额列右对齐，保留两位小数显示

---

## 7. 兼容性要求

### 7.1 浏览器兼容性范围

- Chrome 90+
- Firefox 88+
- Edge 90+
- Safari 14+
- 不支持 Internet Explorer

### 7.2 响应式设计适配标准

- 桌面端（≥1200px）：完整布局
- 平板端（768px ~ 1199px）：表格横向滚动，表单两列变一列
- 移动端（<768px）：表单单列，操作按钮固定在底部

### 7.3 与现有系统模块的兼容性处理

- **路由兼容**：新增 `/ledger/vouchers/create` 和 `/ledger/vouchers/edit/:voucherId`，不影响现有 `/ledger/vouchers/step/1~5` 和 `/accounting/step/1~5`
- **数据兼容**：新凭证仍写入 `Voucher` 和 `AccountingEntry`，不影响现有报表、总账、明细账
- **API 兼容**：新增 `/api/vouchers` 独立路由，不影响现有 `/api/entries` 和 `/api/import-jobs/manual-entries`
- **Step 流程兼容**：手工录入入口仍可从 Step1 选择"传统人工录入凭证"进入 Step2，并保留跳转到独立录入页的能力
- **来源标识兼容**：手工录入凭证来源统一标记为 `manual_entry`，与 AI 生成 `ai_generated`、导入 `import` 区分

---

## 8. 开发规范与质量保障

### 8.1 严格遵循项目现有代码规范

- 后端：snake_case 命名、Pydantic Schema 校验、Decimal 金额计算、业务语义异常
- 前端：PascalCase 组件、camelCase 接口属性、TypeScript 类型定义、Ant Design 组件
- 财务规则：借贷平衡、已结账期间不可修改、金额精度 2 位小数、凭证号唯一性
- 项目规则：边界控制、bugfix 不扩功能、导航任务不改业务逻辑、六级完成标准

### 8.2 单元测试（目标覆盖率不低于 80%）

| 测试目标 | 覆盖场景 | 预期结果 |
|----------|----------|----------|
| 创建凭证 | 正常 1 借 1 贷 | 成功，返回 voucher_id |
| 创建凭证 | 多借多贷平衡 | 成功 |
| 创建凭证 | 借贷不平衡 | 抛出 VoucherBalanceError |
| 创建凭证 | 已结账期间 | 抛出 PeriodClosedError |
| 创建凭证 | 凭证号重复 | 抛出 VoucherDuplicateError |
| 编辑凭证 | 修改分录后平衡 | 成功，旧分录被替换 |
| 编辑凭证 | 修改已复核凭证 | 抛出 VoucherStateError |
| 删除凭证 | 删除草稿 | 成功 |
| 删除凭证 | 删除已过账凭证 | 抛出 VoucherStateError |
| 查询凭证 | 按条件筛选 | 返回正确结果 |
| 复核凭证 | 复核草稿 | 状态变为 verified |
| 入账凭证 | 入账已复核凭证 | 状态变为 posted |

### 8.3 集成测试验证功能完整性

- 测试场景：
  1. 前端录入凭证 → 后端保存 → 列表查询 → 编辑 → 删除
  2. 录入不平衡凭证 → 系统拒绝
  3. 已结账期间录入 → 系统拒绝
  4. 凭证复核 → 入账 → 取消过账

### 8.4 代码审查确保代码质量

- 审查重点：
  - 事务边界是否正确
  - 金额是否使用 Decimal
  - 权限校验是否完整
  - 错误提示是否有业务语义
  - 前端类型定义是否与后端一致
  - 是否引入不必要的依赖

---

## 9. 交付物清单

### 9.1 功能测试报告

- 测试用例列表（至少 20 个用例）
- 测试结果（通过/失败/阻塞）
- 问题清单与修复状态
- 验收结论

### 9.2 性能评估数据

- 凭证列表页响应时间（目标 < 500ms）
- 单张凭证保存响应时间（目标 < 300ms）
- 批量删除 10 张凭证响应时间（目标 < 500ms）
- 并发测试：10 用户同时录入凭证的结果
- 资源占用：CPU、内存峰值

### 9.3 用户操作文档

- 功能说明：手工录入凭证的适用场景
- 操作步骤：
  1. 如何进入手工录入页面
  2. 如何填写凭证头和分录行
  3. 如何保存草稿
  4. 如何编辑和删除凭证
  5. 如何复核和入账
- 常见问题解答：
  - 借贷不平衡怎么办？
  - 凭证号重复怎么办？
  - 已结账期间为什么不能修改凭证？
  - 如何新增科目？

### 9.4 技术实现文档

- 架构设计：前后端分层、数据流
- 接口说明：完整的 API 列表和请求/响应示例
- 数据模型：Voucher、AccountingEntry 表结构、关联关系
- 状态机：凭证状态流转图
- 部署说明：数据库迁移、环境变量配置

---

## 10. 上线与运维准备

### 10.1 部署方案与回滚机制

- 部署步骤：
  1. 执行数据库迁移（新增索引、字段）
  2. 更新后端服务
  3. 更新前端构建产物
  4. 验证接口可用性
  5. 验证前端页面可访问
- 回滚机制：
  - 使用 Git 标签记录部署版本
  - 回滚时恢复上一版本代码和数据库备份
  - 如迁移脚本有问题，使用 Alembic 回退到上一个版本

### 10.2 数据迁移策略

- 新增字段：`AccountingEntry.updated_by`、`updated_at`（可选，允许 NULL 兼容历史数据）
- 新增索引：`voucher_id` 索引（如不存在）、`status` 索引
- 历史数据：
  - 已有 `AccountingEntry` 记录的 `voucher_id` 可能为空，需通过 `voucher_no` 和 `voucher_date` 回填
  - 回填脚本：
    ```python
    # 伪代码
    for entry in entries_without_voucher_id:
        voucher = db.query(Voucher).filter_by(
            ledger_id=entry.ledger_id,
            voucher_no=entry.voucher_no
        ).first()
        if voucher:
            entry.voucher_id = voucher.id
    ```

### 10.3 监控指标与告警机制

| 指标 | 告警阈值 | 说明 |
|------|----------|------|
| 凭证保存接口响应时间 | > 500ms | 连续 5 分钟触发 |
| 凭证列表查询响应时间 | > 1s | 连续 5 分钟触发 |
| 凭证保存失败率 | > 5% | 连续 5 分钟触发 |
| 数据库连接错误 | > 0 | 立即触发 |
| 未处理异常数 | > 10/分钟 | 立即触发 |

---

## 11. 与现有 spec 的对应关系

| 本方案章节 | 相关 spec | 说明 |
|-----------|----------|------|
| 手工录入 UI 与稳定性 | [improve-manual-voucher-entry-ui](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/improve-manual-voucher-entry-ui/spec.md) | 优化录入 UI、凭证字号拆分、期间默认、科目选择、对方单位控制 |
| 输入模式统一 | [unify-voucher-input-modes](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/unify-voucher-input-modes/spec.md) | 统一 AI 和手工路径产物，标准凭证字段 |
| 复核与入账语义 | [clarify-voucher-review-posting-flow](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/clarify-voucher-review-posting-flow/spec.md) | 草稿 → 复核 → 确认入账流程 |
| 多步骤流程恢复 | [restore-voucher-management-step-flow](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/restore-voucher-management-step-flow/spec.md) | 凭证管理多步骤菜单和路由 |
| Step4 真实复核 | [accounting-step4-real-review](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/accounting-step4-real-review/spec.md) | 真实分录加载与复核 |

---

## 12. 变更记录

| 日期 | 变更内容 | 更新人 |
|------|----------|--------|
| 2026-07-01 | 初始创建"手工录入并管理凭证"功能详细实现方案 | AI 助手 |

---

## 13. 参考文件

- [improve-manual-voucher-entry-ui spec](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/improve-manual-voucher-entry-ui/spec.md)
- [unify-voucher-input-modes spec](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/unify-voucher-input-modes/spec.md)
- [clarify-voucher-review-posting-flow spec](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/clarify-voucher-review-posting-flow/spec.md)
- [restore-voucher-management-step-flow spec](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/restore-voucher-management-step-flow/spec.md)
- [accounting-step4-real-review spec](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/specs/accounting-step4-real-review/spec.md)
- [development-plan-voucher-and-parser.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/development-plan-voucher-and-parser.md)
- [current-risks-and-tasks.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/current-risks-and-tasks.md)
- [backend/app/services/voucher_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/voucher_service.py)
- [backend/app/db/models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py)
- [frontend/src/components/voucher/TraditionalVoucherForm.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/components/voucher/TraditionalVoucherForm.tsx)
- [frontend/src/pages/VoucherQueryPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/VoucherQueryPage.tsx)
