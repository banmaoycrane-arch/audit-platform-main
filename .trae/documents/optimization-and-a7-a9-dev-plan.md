# 优化项与 A7-A9 前端开发详细计划

> **文档类型**: 开发执行计划
> **更新日期**: 2026-07-01
> **关联规划**: [manual-voucher-crud-implementation-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/manual-voucher-crud-implementation-plan.md)
> **关联任务清单**: [current-risks-and-tasks.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/current-risks-and-tasks.md)

---

## 第一部分：优化项处理

### 1.1 优化项清单

| 编号 | 优化项 | 优先级 | 影响范围 | 验收标准 |
|------|--------|--------|----------|----------|
| OPT-1 | **为 `Voucher` 表添加 `period_id` 字段并持久化** | P0 | 数据库、后端服务、前端响应 | 创建/更新凭证时正确保存 `period_id`；`GET /api/vouchers/{id}` 返回真实 `period_id` |
| OPT-2 | **为 `Voucher` 表添加 `attachment_count` 字段并持久化** | P0 | 数据库、后端服务、前端响应 | 创建/更新凭证时正确保存 `attachment_count`；响应返回真实附件数 |
| OPT-3 | 将列表查询过滤从内存迁移到 SQL 层 | P1 | 后端服务 | 在数据库层完成分页+筛选，减少内存占用，提升大数据量下的性能 |
| OPT-4 | 修复测试用例的 SQLite 状态隔离 | P1 | 测试代码 | 单测可独立运行，不受其他测试影响 |
| OPT-5 | 统一 `voucher_no` 拆分与拼装逻辑 | P2 | 后端服务 | 避免 `routes_vouchers.py` 和 `voucher_management_service.py` 中重复定义 `_split_voucher_no` |

### 1.2 OPT-1 详细处理方案

**变更原因**：
- 当前 `Voucher` 表未存储 `period_id`，导致凭证详情和列表无法返回真实期间信息
- 影响后续按期间筛选、结账校验、审计追溯等核心功能

**数据库变更**：

```sql
ALTER TABLE vouchers ADD COLUMN period_id INTEGER REFERENCES accounting_periods(id);
-- 为已有数据回填 period_id
UPDATE vouchers v
SET period_id = (
    SELECT p.id FROM accounting_periods p
    WHERE p.ledger_id = v.ledger_id
      AND p.start_date <= v.voucher_date
      AND p.end_date >= v.voucher_date
    LIMIT 1
);
-- 根据业务需要决定是否加非空约束
ALTER TABLE vouchers ALTER COLUMN period_id SET NOT NULL;
```

> 注意：SQLite 对 `ALTER COLUMN` 支持有限，可能需要重建表，建议使用 Alembic 或 `create_all` 重新建表（开发环境）。

**后端变更**：
- `voucher_management_service.py` 中 `create_voucher_from_request` 和 `update_voucher_from_request` 需将 `period_id` 写入 `Voucher` 对象
- `Voucher` 模型增加 `period_id` 字段映射
- `routes_vouchers.py` 中 `_format_voucher` 和 `_format_voucher_list_item` 返回真实 `period_id`
- `VoucherUpdate` Schema 中 `period_id` 为可选

**前端影响**：
- 凭证详情和列表响应增加 `period_id`，前端可用于期间显示和筛选
- 录入/编辑表单需提交 `period_id`（当前已提交）

### 1.3 OPT-2 详细处理方案

**变更原因**：
- 当前 `attachment_count` 未在 `Voucher` 表中存储，响应中固定返回 0
- 影响凭证完整性展示和后续附件管理

**数据库变更**：

```sql
ALTER TABLE vouchers ADD COLUMN attachment_count INTEGER DEFAULT 0;
```

**后端变更**：
- 写入/更新 `attachment_count` 到 `Voucher` 对象
- 响应返回真实值

**前端影响**：
- 录入/编辑表单中已包含附件数字段，后端保存后即可正确显示

### 1.4 优化项开发时序

| 日期 | 任务 | 负责人 |
|------|------|--------|
| 第 1 天 | 数据库迁移（OPT-1、OPT-2） | 后端开发 |
| 第 1 天 | 更新后端服务层和路由层 | 后端开发 |
| 第 2 天 | 更新 Schema 和测试用例 | 后端开发 |
| 第 2 天 | 列表查询 SQL 优化（OPT-3） | 后端开发 |

---

## 第二部分：A7-A9 前端开发计划

### 2.1 功能需求分析

#### A7：凭证列表页增强

**业务场景**：
财务人员进入凭证管理模块后，需要能够：
1. 查看当前账簿的所有凭证
2. 通过期间、日期、凭证号、摘要等条件筛选
3. 展开查看凭证分录明细
4. 直接新增凭证
5. 编辑草稿状态凭证
6. 删除草稿状态凭证
7. 对复核通过的凭证执行入账
8. 批量删除草稿凭证

**用户角色与权限**：
- 制单人：新增、编辑、删除自己的草稿凭证
- 复核人：复核凭证、查看凭证
- 记账人：入账已复核凭证
- 审计人员：只读查看

#### A8：独立凭证录入页

**业务场景**：
财务人员需要快速手工录入凭证，无需经过文件导入/AI 解析流程。页面应：
1. 提供清晰的凭证头信息录入区域
2. 提供传统纸面样式的分录明细录入区域
3. 支持实时借贷平衡提示
4. 支持保存草稿、提交复核
5. 支持保存并新增、保存并复制
6. 自动建议凭证号

#### A9：独立凭证编辑页

**业务场景**：
财务人员对已保存的草稿凭证进行修改：
1. 从列表页点击编辑按钮进入编辑页
2. 系统加载凭证详情并回填到表单
3. 用户修改凭证头或分录行
4. 保存后整单更新

### 2.2 技术方案设计

#### 2.2.1 路由设计

在现有路由基础上新增：

| 路径 | 页面 | 功能 |
|------|------|------|
| `/ledger/vouchers` | `VoucherQueryPage` | 凭证列表（已存在，增强） |
| `/ledger/vouchers/create` | `VoucherCreatePage` | 新增凭证（新建） |
| `/ledger/vouchers/edit/:voucherId` | `VoucherEditPage` | 编辑凭证（新建） |
| `/ledger/vouchers/step/2?inputMode=manual_entry` | `Step2ImportSource` | 保留原向导入口 |

#### 2.2.2 组件复用策略

- **复用组件**：
  - `TraditionalVoucherForm`：用于凭证录入/编辑的核心表单
  - `VoucherCardView`：用于列表卡片展示（已存在，需增强编辑/入账按钮）
  - `VoucherLineTable`：分录行表格（可独立或复用）

- **新建页面**：
  - `VoucherCreatePage`：新增凭证独立页面，复用 `TraditionalVoucherForm`
  - `VoucherEditPage`：编辑凭证独立页面，复用 `TraditionalVoucherForm`，增加 `mode=edit` 和 `voucherId` 参数

#### 2.2.3 状态管理

- 局部状态：使用 `useState` 管理表单字段、分录行、校验错误
- 全局状态：通过 `useAuthStore` 获取 `currentLedgerId`、`currentUser`
- 服务端状态：通过 API 调用获取凭证详情

#### 2.2.4 前端 API 扩展

在 `frontend/src/api/client.ts` 中新增：

```typescript
createVoucher: (payload: VoucherCreatePayload) => Promise<VoucherResponse>
getVoucher: (voucherId: number) => Promise<VoucherResponse>
updateVoucher: (voucherId: number, payload: VoucherUpdatePayload) => Promise<VoucherResponse>
deleteVoucher: (voucherId: number) => Promise<void>
verifyVoucher: (voucherId: number) => Promise<VoucherResponse>
postVoucher: (voucherId: number) => Promise<VoucherResponse>
```

### 2.3 任务拆解与分配

| 任务编号 | 任务名称 | 描述 | 优先级 | 负责人 | 依赖 |
|----------|----------|------|--------|--------|------|
| A7-1 | 列表页新增"新增凭证"按钮 | 在 `VoucherQueryPage` 工具栏添加按钮，跳转 `/ledger/vouchers/create` | P0 | 前端开发 | OPT-1/2 完成 |
| A7-2 | 列表卡片添加"编辑"按钮 | 草稿状态凭证显示编辑按钮，跳转 `/ledger/vouchers/edit/{voucherId}` | P0 | 前端开发 | OPT-1/2 完成 |
| A7-3 | 列表卡片添加"入账"按钮 | 已复核状态凭证显示入账按钮，调用 `postVoucher` | P0 | 前端开发 | API 已完成 |
| A7-4 | 列表页筛选增强 | 按期间、状态、日期范围筛选 | P1 | 前端开发 | OPT-3 完成 |
| A8-1 | 新建 `VoucherCreatePage` | 独立录入页面，复用 `TraditionalVoucherForm` | P0 | 前端开发 | OPT-1/2 完成 |
| A8-2 | 新增 API 调用接入 | 在 `client.ts` 添加 `createVoucher` 并接入录入页 | P0 | 前端开发 | A8-1 |
| A8-3 | 凭证号自动建议 | 根据当前期间最大凭证号 + 1 建议 | P1 | 前端开发 | A8-1 |
| A9-1 | 新建 `VoucherEditPage` | 独立编辑页面，支持 `voucherId` 参数 | P0 | 前端开发 | A8-1 |
| A9-2 | 编辑模式数据回填 | 调用 `getVoucher` 加载详情并回填表单 | P0 | 前端开发 | A9-1 |
| A9-3 | 更新 API 调用接入 | 在 `client.ts` 添加 `updateVoucher` 并接入编辑页 | P0 | 前端开发 | A9-2 |
| A9-4 | 编辑页状态校验 | 仅草稿状态可编辑，非草稿提示并返回列表 | P0 | 前端开发 | A9-1 |
| QA-1 | 编写前端测试 | 录入、编辑、列表交互测试 | P1 | 测试/QA | A7-3/A9-4 |
| QA-2 | 联调测试 | 前后端完整流程验证 | P0 | 全团队 | 所有开发完成 |
| QA-3 | 代码审查 | 重点审查事务、金额、权限 | P0 | 技术负责人 | QA-2 |

### 2.4 开发时间表

| 周次 | 星期 | 任务 | 输出 |
|------|------|------|------|
| 第 1 周 | 周一 | 处理 OPT-1、OPT-2（数据库迁移 + 后端服务更新） | 后端可正确保存/返回 period_id 和 attachment_count |
| 第 1 周 | 周二 | 处理 OPT-3（列表 SQL 优化）和 OPT-5（代码重构） | 列表查询性能提升 |
| 第 1 周 | 周三 | A7-1 ~ A7-3（列表页增强） | 列表页有新增/编辑/入账按钮 |
| 第 1 周 | 周四 | A8-1 ~ A8-2（独立录入页 + API） | 独立录入页可用 |
| 第 1 周 | 周五 | A9-1 ~ A9-3（独立编辑页 + 回填 + API） | 独立编辑页可用 |
| 第 2 周 | 周一 | A7-4（筛选增强）、A8-3（凭证号建议）、A9-4（状态校验） | 体验优化完成 |
| 第 2 周 | 周二 | QA-1（前端测试） | 测试用例完成 |
| 第 2 周 | 周三 | QA-2（联调测试） | 问题清单与修复 |
| 第 2 周 | 周四 | QA-3（代码审查）与修复 | 审查报告与修复记录 |
| 第 2 周 | 周五 | 功能验收与性能优化 | 验收报告 |

### 2.5 质量保障措施

#### 2.5.1 代码审查重点

- 所有 API 调用是否携带 `Authorization` 和 `X-Ledger-Id` 头部
- 表单提交前是否进行前端校验
- 金额是否统一保留 2 位小数
- 编辑页是否校验凭证状态（仅草稿可编辑）
- 凭证号唯一性校验是否基于后端响应
- 错误提示是否使用中文业务语义
- 是否避免重复定义 `_split_voucher_no` 等工具函数

#### 2.5.2 测试覆盖

| 测试类型 | 数量 | 覆盖率目标 |
|----------|------|------------|
| 后端单元测试 | 新增 9 个，后续补充 6 个 | ≥ 80% |
| 前端交互测试 | 8 个 | 核心流程覆盖 |
| 集成测试 | 5 个 | 端到端覆盖 |

#### 2.5.3 性能指标

- 凭证列表页首屏加载 < 500ms（1000 条以内）
- 单张凭证保存 < 300ms
- 编辑页详情加载 < 200ms

### 2.6 资源调配

| 角色 | 人数 | 职责 |
|------|------|------|
| 后端开发 | 1 人 | 优化项处理、API 调整、测试支持 |
| 前端开发 | 1 人 | A7-A9 页面开发、API 接入、交互优化 |
| 测试/QA | 1 人 | 测试用例、联调测试、验收 |
| 技术负责人 | 0.5 人 | 方案评审、代码审查、技术决策 |
| 财务业务专家 | 0.3 人 | 需求确认、验收测试、问题判定 |

### 2.7 风险管理

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| SQLite 迁移限制导致 `ALTER COLUMN` 失败 | 中 | 高 | 开发环境采用 `create_all` 重建；生产使用 Alembic 分步迁移 |
| 前端类型与后端 Schema 不一致 | 中 | 中 | 每次后端 Schema 变更后同步更新 `client.ts` 类型，并运行 `tsc -b` |
| 凭证号并发冲突 | 低 | 中 | 后端依赖唯一约束兜底，前端捕获 409 错误提示 |
| 已入账凭证误编辑 | 低 | 高 | 前后端双重校验状态，非草稿状态禁用编辑入口 |
| 测试数据污染 | 中 | 中 | 测试使用独立数据库文件，每个测试用例清理数据 |
| 期间状态变更导致历史凭证无法编辑 | 中 | 中 | 编辑和删除时校验当前期间状态，已结账期间禁止修改 |

---

## 第三部分：验收标准

### 3.1 优化项验收标准

- [ ] `Voucher` 表包含 `period_id` 和 `attachment_count` 字段
- [ ] 创建凭证时正确保存 `period_id` 和 `attachment_count`
- [ ] 更新凭证时正确更新 `period_id` 和 `attachment_count`
- [ ] `GET /api/vouchers` 和 `GET /api/vouchers/{id}` 返回真实字段值
- [ ] 列表查询按数据库条件过滤，分页正确
- [ ] 测试用例全部通过

### 3.2 A7-A9 验收标准

- [ ] 凭证列表页有"新增凭证"按钮，点击跳转独立录入页
- [ ] 草稿状态凭证卡片显示"编辑"按钮，点击跳转独立编辑页
- [ ] 已复核状态凭证卡片显示"入账"按钮，点击后状态变为已过账
- [ ] 独立录入页可填写凭证头、分录行，保存后生成草稿凭证
- [ ] 独立编辑页可加载已有凭证，修改后整单更新
- [ ] 借贷不平衡时保存按钮禁用，并提示差额
- [ ] 已结账期间凭证不可编辑/删除
- [ ] 非草稿状态凭证不可编辑
- [ ] 后端单元测试覆盖率 ≥ 80%
- [ ] 端到端流程测试通过

---

## 第四部分：后续工作衔接

A7-A9 完成后，将继续推进：
- 文件解析引擎 → 凭证草稿直接链路（任务 B）
- 数据库迁移冲突修复（任务 C）
- 测试稳定性提升（任务 D）
- 审计工作流 API/前端（任务 F）
- 按业务循环审计（任务 G）

---

## 变更记录

| 日期 | 变更内容 | 更新人 |
|------|----------|--------|
| 2026-07-01 | 初始创建优化项与 A7-A9 开发计划 | AI 助手 |

---

## 参考文件

- [manual-voucher-crud-implementation-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/manual-voucher-crud-implementation-plan.md)
- [current-risks-and-tasks.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/current-risks-and-tasks.md)
- [backend/app/api/routes_vouchers.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_vouchers.py)
- [frontend/src/pages/VoucherQueryPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/VoucherQueryPage.tsx)
- [frontend/src/components/voucher/TraditionalVoucherForm.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/components/voucher/TraditionalVoucherForm.tsx)
- [frontend/src/api/client.ts](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/api/client.ts)
