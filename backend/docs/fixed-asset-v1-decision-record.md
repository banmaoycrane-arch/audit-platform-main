# 固定资产模块 v1.0 — 决策记录（开发起点）

> **文档性质**：已决议的产品/架构决策记录（**非实现代码**）  
> **状态**：已确认，待开发  
> **决策日期**：2026-07  
> **关联文档**：
> - 表结构草案：[fixed-asset-register-schema-draft.md](./fixed-asset-register-schema-draft.md)（v0.3-draft）
> - 平台底线与 Tag 原则：[tag-vs-account-hierarchy.md](./tag-vs-account-hierarchy.md) §1.1–§1.2
> - 引擎与模块边界：[engine-architecture.md](./engine-architecture.md)

**本文档用途**：固定 v1.0 开发范围与架构边界，作为后续 migration / API / UI 开发的**唯一决策起点**。当前阶段**不编写业务代码**，仅保留讨论结论。

---

## 1. 业务背景（已确认）

典型厂建场景：**整体投资约 8000 万**，建设期较长。

| 阶段 | 实务 | 系统应表达 |
|------|------|------------|
| 建设期 | 按 **性质**（材料、人工、资本化利息、车间等）归集 1604，**尚无具体可折旧资产** | 成本池归集，不必先有卡片 |
| 竣工 | 按管理口径（如「三期扩产」、产线、厂房）**拆成多张卡片** | 1 池 → N 卡，事件留痕 |
| 投产后 | 维修扩建增原值、组件替换、合并/再拆分、年限变更/加速/重算 | 事件链 +（v1.1 起）政策版本链 |
| 全程 | 固定资产定义在准则下**相对动态** | **不变量：留痕 + 多处勾稽** |

---

## 2. 与现有体系的兼容承诺

固定资产模块**必须**接入现有分录与 Tag 体系，**不得**新建平行标签库或替代分录存储金额。

### 2.1 分录层（不变）

| 现有真值 | 固定资产模块用法 |
|----------|------------------|
| `accounting_entries` | 1604 在建归集、1601 转固/资本化、1602 累计折旧、6602 折旧费用等 **金额与借贷方向唯一来源** |
| `AccountingEntry` ↔ `EntryTag`（1:N） | 卡片/池 **只通过 `entry_id` 读 Tag**，不在 Register 宽表重复存类别、项目、部门 |
| `resolved_account_code` | 派生卡片/池草稿的科目触发条件（1601 / 1604 等） |
| `ledger_id` | 池、卡片、链接、事件、勾稽任务 **全部账簿隔离** |

**禁止**：把金额、借贷、正式科目迁入 Tag 或仅用 Tag 行表达会计事实（§1.1 底线 A）。

### 2.2 Tag 层（复用，不新建平行体系）

固定资产 **不新建** 独立向量库或模块私有标签表；复用 `TagCategory` + `EntryTag` + 现有 Qdrant 同步（`entry_tag_vector_service`，`ledger_id` 隔离）。

#### 科目 → Tag 映射（与现网解析一致）

来源：`account_tag_resolution_service._STRUCTURED_NAME_TAG_ACCOUNTS`、`tag_category_constants.STANDARD_VECTOR_CATEGORY_CODES`。

| 科目 | 双 Tag（解析规则已存在） | 用途 |
|------|--------------------------|------|
| **1601** 固定资产 | `fixed_asset_class` + `fixed_asset_item` | 竣工后卡片语义；派生卡片草稿 |
| **1602** 累计折旧 | `fixed_asset_class` + `fixed_asset_item` | 折旧勾稽、按类别汇总 |
| **1604** 在建工程 | `cip_category` + `cip_project` | 建设期性质 + 项目（如三期扩产） |

#### 可叠加的共享 Tag（已有分类，按需挂分录）

| TagCategory | 场景 |
|-------------|------|
| `project` | 管理项目口径（可与 `cip_project` 并存或互补） |
| `department` | 使用部门 |
| `cost_element` | 成本要素补充（**v1.0 不新建 `cip_cost_nature`**） |
| `expense_type` | 费用性质辅助 |

#### 已决议：Tag 扩展策略

| 议题 | 决议 |
|------|------|
| 是否新建 `cip_cost_nature` | **否** — v1.0 用现有 `cip_category`（1604 主 Tag）+ 可选 `cost_element` |
| 卡片是否存 class/item/部门/项目列 | **否** — 经 `capitalization_entry_id` → `entry_tags` JOIN 读取 |
| UI 短标题 | 可选 `display_label`；**权威名称仍以 EntryTag `fixed_asset_item` 为准** |

### 2.3 Register 层（未来新增，模式与现有模块一致）

与 `Contract`、`Invoice` 等 Register 相同模式：

- Register 存 **模块独一份核心**（卡片号、原值、折旧政策、状态、与分录 FK）
- 分析维度走 **EntryTag**
- 列表 API 层 JOIN Tag 填充展示字段，**不落库**

### 2.4 内控缺陷（复用现有通道）

勾稽差异写入现有 **内控缺陷清单**（`/ledger/control-defects`），metadata 带 `fixed_asset_id` / `pool_id` / `entry_id`。**只警示，不自动改分录、不静默改卡片。**

---

## 3. 架构不变量（开发时不可突破）

1. **金额真值在分录**；池/卡片金额为运行值 + 勾稽视图。  
2. **Tag 标注分录，不替代分录**（§1.1）。  
3. **Register 最小核心 + Tag 辅助**（§1.2 原则 D）。  
4. **事件只追加、不物理删除历史**（`card_events` + `entry_links` 留痕）。  
5. **差异 → 内控缺陷**，不静默调账。

---

## 4. 数据模型（已决议，待 migration）

详细字段见 [fixed-asset-register-schema-draft.md](./fixed-asset-register-schema-draft.md)。

| 表 | 用途 | v1.0 |
|----|------|------|
| `fixed_asset_cip_pools` | 在建成本池 | ✅ |
| `fixed_asset_pool_entry_links` | 池 ↔ 1604 分录 | ✅ |
| `fixed_asset_register` | 固定资产卡片 | ✅ |
| `fixed_asset_entry_links` | 卡片 ↔ 分录（含 `allocated_amount`） | ✅ |
| `fixed_asset_card_events` | 全生命周期事件 | ✅ |
| `fixed_asset_depreciation_policies` | 折旧政策版本链 | ⏸ v1.1（v1.0 政策字段在卡片上） |

**刻意不建**：资产类别表、部门/项目冗余列、模块私有 Tag 表。

---

## 5. 主业务流程（已决议）

### 5.1 默认路径：池优先

```text
建设期：fixed_asset_cip_pools(collecting)
        + 1604 分录 + EntryTag(cip_category, cip_project, …)
        + pool_entry_links
        （可无 fixed_asset_register 行）

竣工：  card_events(pool_to_cards)
        → 多张 fixed_asset_register(active)
        + cip_to_fa 转固分录 + entry_links
        SUM(卡片.original_cost) = 池已转固金额（勾稽）

投产后：折旧引擎 → 1602/6602 分录 → 与 GL 勾稽
```

| 场景 | 做法 |
|------|------|
| 整体厂建、竣工前无具体资产 | **仅成本池**，不建卡片 |
| 1:1 简单转固 | 1 池 → 1 卡（同一模型） |
| 1:N 竣工拆卡（8000 万 → 多资产） | **`pool_to_cards`**（主路径） |
| 直接购入（无 1604） | 1601 分录 + 双 Tag → 卡片草稿（可跳过池） |

### 5.2 卡片编号 `asset_no`

- 账簿内唯一；配置键 `LedgerSettings.fixed_asset_numbering`（JSON）
- 模式：`manual` / `auto` / `auto_with_manual_override`（**默认**）
- 模板：`{prefix}{seq}{suffix}`；拆分衍生 `{parent}-S{n}`；草稿可 `DRAFT-{entry_id}`
- **编号与 Tag 语义不绑定**

### 5.3 一条分录 → 多张卡片

- **必须支持**；`entry_links.allocated_amount` 分摊
- `SUM(allocated_amount)` = 分录行金额（容差 0.01）
- 事务内完成 + `card_events.split` 留痕

### 5.4 累计折旧

```text
引擎计提 → 更新卡片 accumulated_depreciation
         → 写 entry_links(depreciation) + 生成/关联 draft 分录
         → 期末 SUM(卡片) vs 1602 GL → 不一致 = 内控缺陷
```

**不做**：用 1602 分录反写静默覆盖卡片。

---

## 6. v1.0 固定开发范围（已确认）

### 6.1 纳入 v1.0（P0）

| 能力 | 说明 |
|------|------|
| 成本池 CRUD + 分录挂接 | `pool_collect`，池 ↔ 1604 勾稽 |
| 竣工拆卡 | `pool_to_cards` 向导/ API |
| 卡片 Register | 列表/详情/确认；从 1601 分录 + Tag 派生草稿 |
| 分录链接 | `fixed_asset_entry_links`，含分摊 |
| 事件留痕 | P0 事件类型见 §6.3 |
| 折旧引擎 | **仅直线法**（`straight_line`） |
| 勾稽 + 内控缺陷 | P0 缺陷码见 §6.4 |
| 模块注册 | `MODULE_DEFINITIONS.fixed_asset_register` |
| 前端 | 替换 `FixedAssetsWorkspace` 占位（池、卡片、拆卡、计提入口） |
| 编号规则 | `LedgerSettings.fixed_asset_numbering` |

### 6.2 明确排除 v1.0（后续版本）

| 能力 | 目标版本 |
|------|----------|
| `fixed_asset_depreciation_policies` 版本链表 | v1.1 |
| 年限/方法变更（完整 policy 链 + 过渡勾稽） | v1.1 |
| `capitalized_repair` / `component_replace` | v1.1 |
| 卡片 merge、部分处置（完整） | v1.1 |
| 池合并 `pool_merge` | v1.2 |
| 加速折旧、追溯调整 | v1.2 |
| 双倍余额递减、工作量法 | v1.2+ |
| 池 `budget_amount` 投资进度 KPI | v1.0 仅存字段，不做 KPI UI |

### 6.3 v1.0 事件类型范围

| event_type | v1.0 |
|------------|------|
| `pool_collect` | ✅ |
| `pool_to_cards` | ✅ |
| `cip_to_fa` | ✅ |
| `split` | ✅ |
| `dispose` | ✅ 基础（全部处置） |
| `dep_policy_change` | ⏸ 简化为改卡片字段 + 可选 event 记录，无版本链表 |
| `merge` / `capitalized_repair` / `component_replace` / `pool_merge` / `dep_accelerated` / `dep_re_basis` | ❌ v1.1+ |

### 6.4 v1.0 内控缺陷码（实现时注册）

| 缺陷码 | 勾稽点 |
|--------|--------|
| `fa_pool_vs_cip_gl` | 池 allocated 合计 vs 1604 |
| `fa_pool_card_split_gap` | 拆卡原值合计 vs 池已转固金额 |
| `fa_entry_allocation_mismatch` | 分录分摊 vs 行金额 |
| `fa_accum_dep_reconcile_gap` | 卡片累计折旧 vs 1602 |

v1.1 追加：`fa_register_vs_gl_original_cost`、`fa_dep_policy_transition_gap`、`fa_capitalized_repair_gap`（见 schema 草案 §4.4）。

---

## 7. 与现有代码的对接点（开发时只读这些，不改 Tag 体系）

| 组件 | 路径 | 用途 |
|------|------|------|
| 分录模型 | `backend/app/db/models.py` — `AccountingEntry`, `EntryTag` | FK 与 JOIN |
| Tag 分类常量 | `backend/app/config/tag_category_constants.py` | 不重复 seed FA 专用 category |
| 科目 Tag 解析 | `backend/app/services/doc_parsing/account_tag_resolution_service.py` | 1601/1604 双 Tag 派生 |
| 向量同步 | `entry_tag_vector_service`（现有） | 卡片语义检索仍走 EntryTag |
| Register 范例 | `models.Contract`, `models.Invoice` | module_register 模式 |
| 内控缺陷 UI | `/ledger/control-defects` | 勾稽结果展示 |
| 前端壳 | `frontend/src/pages/Workspaces/FixedAssetsWorkspace.tsx` | v1.0 替换占位 |

---

## 8. 开发顺序建议（v1.0 启动时）

```text
1. Alembic migration（5 表，不含 depreciation_policies）
2. SQLAlchemy models + Pydantic schemas
3. fixed_asset_service：池、拆卡、卡片 CRUD
4. entry 派生：1601/1604 + Tag → 草稿
5. depreciation_engine（直线法）+ draft 分录生成
6. reconcile job + control_defect 码注册
7. module_register_service 接入 + API routes
8. 前端：池列表、拆卡向导、卡片列表、计提页
9. LedgerSettings.fixed_asset_numbering
10. 测试：池勾稽、拆卡分摊、折旧勾稽、Tag JOIN 展示
```

---

## 9. 决策签核清单

以下项 **2026-07 讨论已确认**，后续开发默认遵循，变更需更新本文档：

- [x] 建设期默认 **成本池优先**，竣工 **`pool_to_cards`** 拆卡  
- [x] v1.0 = 池 + 拆卡 + **直线法折旧** + 4 项 P0 勾稽  
- [x] 折旧政策版本链 **推迟至 v1.1**  
- [x] 1604 Tag 复用 **`cip_category` + `cip_project`**，不新建 `cip_cost_nature`  
- [x] 1601 Tag 复用 **`fixed_asset_class` + `fixed_asset_item`**  
- [x] 差异进 **control-defects**，不自动调账  
- [x] **兼容现有 EntryTag / 分录体系**，不新建平行 Tag  
- [x] 当前阶段 **仅文档，不写业务代码**

---

## 10. 文档索引

| 文档 | 角色 |
|------|------|
| **本文档** | 决策记录、v1.0 范围、兼容性约束 |
| [fixed-asset-register-schema-draft.md](./fixed-asset-register-schema-draft.md) | 表结构、事件类型全集、DDL 草案 |
| [tag-vs-account-hierarchy.md](./tag-vs-account-hierarchy.md) | 平台 §1.1/§1.2 底线 |
| [engine-architecture.md](./engine-architecture.md) | 引擎与模块调度 |

---

*最后更新：2026-07 — 讨论定稿，待 v1.0 开发启动。*
