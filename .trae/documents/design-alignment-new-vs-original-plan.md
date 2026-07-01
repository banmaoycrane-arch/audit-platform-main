# 新架构内容与原始设计理念对齐计划

## 1. Summary（目标与结论）

基于最新讨论的 **“Organization → Legal Entity → Reporting Entity → Sub Legal” 三层主体模型** 和 **“统一数据底座 + 多视图分析架构”**，与项目已有的设计理念、核心概念边界、数据模型和 spec 体系进行全面对齐，明确冲突点、重叠点，并决定采用 **“补充更清晰方案”** 而非 **“推翻原方向”** 的演进策略。

最终输出：
- 新旧概念映射表
- 冲突点清单与处理建议
- 需要补充或调整的 spec 清单
- 推荐的实施顺序
- 验证方式

---

## 2. Current State Analysis（当前状态分析）

### 2.1 原始设计理念

根据 `.trae/documents/core-business-concepts-boundary.md`、`requirements-domain-index.md`、`.trae/specs/team-multi-ledger-management/spec.md`、`.trae/specs/ledger-register-project-concept-unification/spec.md`、`.trae/specs/entity-semantic-mapping/spec.md`、`.trae/specs/internal-accounting-unit/spec.md` 和 `backend/app/db/models.py` 的确认，原始设计采用“协作 + 核算 + 项目 + 语义主体”多维分层：

```text
User
  └─ Team：协作和权限范围（事务所 / 企业组织）
       └─ Ledger：正式会计账簿 / 财务数据边界
            ├─ AccountingPeriod / AccountingEntry / OpeningBalance
            ├─ SourceFile / ImportJob
            ├─ ChartOfAccounts / Counterparty
            └─ Accounting Entity / Entity（语义映射）
       └─ Project：工作任务边界，可关联多个 Ledger

Register：业务台账（银行日记账、发票、固定资产卡片等）
Entity / EntityScope / VirtualEntitySet / AccountingUnit：多维度主体与内部核算单位
```

### 2.2 关键概念定位

| 概念 | 原始定位 | 代码体现 |
|---|---|---|
| Team | 协作与权限组织，不直接过滤财务数据 | `backend/app/models/team.py` |
| Ledger | 正式财务数据隔离边界，所有凭证/期间/报表以 `ledger_id` 为主 | `backend/app/models/ledger.py`；所有业务表含 `ledger_id` |
| Project | 工作任务边界，可关联多个 Ledger | `backend/app/models/project.py`、`project_ledger.py` |
| Organization | 早期“默认企业”概念，已被弱化为历史兼容字段 | `backend/app/db/models.py` 第 8 行 |
| Entity | 会计主体 / 法律主体 / 纳税主体 / 管理主体的语义映射实体 | `backend/app/db/models.py` 第 146 行 |
| EntityScope | 主体范围（合并 / 税务 / 管理 / 法律） | `backend/app/db/models.py` 第 208 行 |
| VirtualEntitySet | 虚拟主体集合，如“XX集团” | `backend/app/db/models.py` 第 276 行 |
| AccountingUnit | 内部核算单位（项目 / 部门 / SKU / 渠道等） | `backend/app/db/models.py` 第 488 行 |

### 2.3 新方案的核心内容

最新讨论形成的新方案包括：

1. **三层主体模型**：Organization → Legal Entity → Reporting Entity
2. **Sub Legal（次级法律载体）**：分公司等具有工商资质但无法人资格的主体
3. **统一数据底座 + 多视图分析架构**：一套原始数据、多套口径模板、多场景切换

### 2.4 冲突与重叠识别

#### 冲突点 1：Organization 一词被占用且定位不同

- **原始设计**：`Organization` 是早期“默认企业”概念，被 `core-business-concepts-boundary.md` 明确弱化为历史兼容字段，新需求不应作为正式财务主边界。
- **新方案**：`Organization` 是集团顶层组织，归集全部 Legal Entity，用于合并报表和内部关联方识别。
- **影响**：若直接提升 `Organization` 为顶层，需要重新定义 Team 与 Organization 的关系，并处理历史字段冲突。

#### 冲突点 2：Ledger 的定位是否需要下沉

- **原始设计**：`Ledger` 是最高核算边界，所有正式财务数据以 `ledger_id` 为强过滤条件。
- **新方案**：`Ledger` 可能只是 `Reporting Entity` 或 `Legal Entity` 下的一个“账簿视图”，核算主体应是 `Reporting Entity`。
- **影响**：若将 `ledger_id` 降级，所有 `accounting_entries`、`accounting_periods`、`opening_balances` 等表的主过滤口径需要重新设计，动摇现有数据隔离基础。

#### 冲突点 3：Entity 已有完整多维主体模型

- **原始设计**：`Entity` 是语义映射实体，通过 `is_accounting_entity`、`is_tax_entity`、`is_legal_entity`、`is_management_entity` 标志支持多维度主体，配合 `EntityScope`、`VirtualEntitySet` 支持动态合并和虚拟集合。
- **新方案**：提出独立的 `Legal Entity`、`Reporting Entity`、`Sub Legal`。
- **影响**：新方案与 `Entity` 模型在功能上高度重叠，若另起炉灶会导致数据模型冗余和概念混乱。

#### 冲突点 4：统一数据底座与现有 ledger_id 强隔离架构的冲突

- **原始设计**：数据按 `ledger_id` 强隔离，报表服务按 `organization_id` + `period_id` 计算，未支持跨 Ledger 合并。
- **新方案**：提出统一数据底座，支持项目、法人、集团多维度切换和多口径分析。
- **影响**：需要在现有 `ledger_id` 隔离基础上新增跨 Ledger 聚合层，同时不破坏记账闭环和审计闭环。

### 2.5 兼容点识别

| 新方案概念 | 可映射到的原始设计 |
|---|---|
| Organization（集团容器） | 现有 `Organization` 表升级 + `VirtualEntitySet` 的集团集合能力 |
| Legal Entity（法律主体） | 现有 `Entity` 的 `is_legal_entity = true` 的记录 |
| Sub Legal（分公司） | 现有 `Entity` 的 `parent_id` 层级或 `VirtualEntitySet` 的二级成员 |
| Reporting Entity（报表主体） | 现有 `Entity` 的 `is_accounting_entity = true` 或 `EntityScope` 的合并范围 |
| 统一数据底座 + 多视图分析 | 现有 `EntityScope`、`VirtualEntitySet`、`AccountingUnit` 支持的动态范围切换 + 新增口径规则引擎 |

---

## 3. Proposed Changes（建议方案）

### 3.1 总体策略：补充更清晰方案，不改原方向

**理由**：
- 原始设计已经具备较完整的主体分层和语义映射能力，`Entity`、`EntityScope`、`VirtualEntitySet`、`AccountingUnit` 等模型可以承载新方案的核心诉求。
- 直接推翻原始设计会导致大量已有代码、spec、数据模型重构，风险高且不必要。
- 新方案的价值在于**概念更清晰、业务表述更贴近审计/财务实务**，应在现有架构基础上进行概念澄清和补充，而非替换。

### 3.2 概念映射表（推荐落地）

| 新方案概念 | 原始设计中的映射 | 说明 |
|---|---|---|
| Organization | `Organization` 表升级 + `VirtualEntitySet` | 提升为集团容器，但保留 Team 作为协作边界 |
| Primary Legal（完整法人） | `Entity` 中 `is_legal_entity = true` 且 `parent_id = null` | 独立法律主体 |
| Sub Legal（分公司） | `Entity` 中 `is_legal_entity = true` 且 `parent_id = Primary Legal` | 次级法律载体，法律责任归属 Primary Legal |
| Reporting Entity（报表主体） | `Entity` 中 `is_accounting_entity = true` | 会计核算边界 |
| Accounting Unit（业务单元） | 现有 `AccountingUnit` | 项目、产品线、门店等内部管理维度 |
| Ledger（账簿） | 现有 `Ledger` | 作为 Reporting Entity 下的具体核算账簿，不降级为“视图” |

### 3.3 需要补充的文档/规格

#### 3.3.1 新增规格：《主体层级与口径映射规格》

- **文件**：`.trae/specs/entity-legal-reporting-sub-alignment/spec.md`
- **内容**：
  - 明确 Organization、Primary Legal、Sub Legal、Reporting Entity、Accounting Unit、Ledger 六层定义。
  - 给出与现有 `Entity`、`EntityScope`、`VirtualEntitySet`、`AccountingUnit`、`Ledger` 的映射关系。
  - 规定各层在合同、分录、报表、合并、审计、税务、融资场景中的使用规则。
  - 明确 `Sub Legal` 与 `Reporting Entity` 的区别：Sub Legal 有工商资质，可对外签约；Reporting Entity 仅内部核算。

#### 3.3.2 补充规格：《统一数据底座与多视图分析架构规格》

- **文件**：`.trae/specs/unified-data-foundation-multi-view/spec.md`
- **内容**：
  - 定义“统一数据底座”：以现有原始业务数据（合同、发票、凭证、资金）为基础，不重复存储。
  - 定义“口径规则引擎”：税务口径、管理考核口径、融资披露口径三套规则参数独立维护。
  - 定义“多视图看板”：按项目 / 法人 / 集团切换颗粒度，按税务 / 考核 / 融资切换场景。
  - 定义“留痕层”：每次切换记录口径参数、颗粒度、操作用户、时间。
  - 明确与现有 `ledger_id` 强隔离架构的兼容方式：跨 Ledger 聚合基于 `EntityScope` 或 `VirtualEntitySet` 计算，不破坏记账闭环。

#### 3.3.3 调整规格：《财务报表与合并报表主体范围规格》

- **文件**：`.trae/specs/financial-statements/spec.md`（补充）
- **内容**：
  - 明确报表 API 参数从 `organization_id` 迁移到 `reporting_entity_id` 或 `entity_scope_id`。
  - 支持按 Legal Entity、Reporting Entity、Organization 三个层级出具报表。
  - 定义合并报表的抵消规则和跨 Ledger 聚合逻辑。

#### 3.3.4 调整规格：《多账簿管理与项目关联规格》

- **文件**：`.trae/specs/team-multi-ledger-management/spec.md`（补充）
- **内容**：
  - 明确 `Ledger` 与 `Reporting Entity` 的关系：一个 Reporting Entity 可拥有多个 Ledger，但一个 Ledger 只能归属一个 Reporting Entity。
  - 明确 `Project` 的核算范围：Project 可以关联一个或多个 Reporting Entity，而不仅仅是 Ledger。
  - 保留 Team 作为协作权限边界，不将其替换为 Organization。

### 3.4 需要调整但不推倒重来的代码模块

| 模块 | 调整内容 | 文件路径 |
|---|---|---|
| `Entity` 模型 | 增加 `legal_type` 字段（`primary_legal` / `sub_legal` / `reporting_entity` / `accounting_unit`）以支持新方案概念 | `backend/app/db/models.py` |
| `Ledger` 模型 | 增加 `reporting_entity_id` 字段，明确 Ledger 归属的 Reporting Entity | `backend/app/models/ledger.py` |
| `Organization` 模型 | 升级字段，增加 `headquarters_entity_id`、`consolidation_scope` 等 | `backend/app/db/models.py` |
| `Project` 模型 | 支持关联 Reporting Entity，而不只是 Ledger | `backend/app/models/project.py` |
| 报表服务 | 支持按 `reporting_entity_id` 和 `entity_scope_id` 计算 | `backend/app/services/financial_statements_service.py` |
| 权限过滤 | 在现有 `ledger_id` 过滤基础上增加 `entity_scope` 过滤 | `backend/app/core/dependencies.py` 等 |

### 3.5 不需要调整的部分

| 模块 | 理由 |
|---|---|
| `ledger_id` 作为凭证/期间/期初余额的主过滤口径 | 保留，Ledger 作为 Reporting Entity 下的具体核算账簿，数据隔离仍然有效。 |
| `Team` 作为协作权限边界 | 保留，Organization 作为集团容器，Team 作为工作协作组织，两者不冲突。 |
| `AccountingUnit` 作为内部核算维度 | 保留，与 Sub Legal / Reporting Entity 明确区分。 |
| 双引擎解析引擎 | 解析层主要处理文件内容，主体层级变化对其核心逻辑影响较小。 |

---

## 4. Assumptions & Decisions（假设与决策）

### 4.1 关键决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| 是否推翻原始设计？ | 否 | 原始设计已具备主体分层能力，推倒重构成本高、风险大。 |
| 是否新增独立表？ | 优先复用 `Entity` 表，新增 `legal_type` 等字段 | 避免数据模型冗余，保持概念一致性。 |
| Organization 是否取代 Team？ | 否 | Organization 是集团容器，Team 是协作组织，职责不同。 |
| Ledger 是否降级为视图？ | 否 | Ledger 仍作为正式核算账簿，Reporting Entity 是其上层聚合维度。 |
| 统一数据底座是否破坏 `ledger_id` 隔离？ | 否 | 跨 Ledger 聚合通过 `EntityScope` / `VirtualEntitySet` 计算，原始数据仍按 Ledger 隔离。 |

### 4.2 假设

- 现有 `Entity` 表已具备足够字段扩展 `legal_type` 枚举。
- `EntityScope` 和 `VirtualEntitySet` 可以支持集团、合并报表、多法人范围的动态切换。
- 用户接受“补充概念澄清和规格”而非“立即重构代码”的渐进策略。

---

## 5. Verification Steps（验证步骤）

1. **文档一致性验证**：
   - 检查 `.trae/specs/entity-legal-reporting-sub-alignment/spec.md` 是否与 `core-business-concepts-boundary.md` 无冲突。
   - 检查 `.trae/specs/unified-data-foundation-multi-view/spec.md` 是否与现有 `ledger_id` 隔离架构兼容。

2. **概念映射验证**：
   - 将新方案六层主体（Organization、Primary Legal、Sub Legal、Reporting Entity、Accounting Unit、Ledger）逐一映射到现有模型字段，确认无遗漏。

3. **代码影响验证**：
   - 检查 `backend/app/db/models.py` 中 `Entity`、`Organization`、`Ledger` 字段是否能支持新方案，无需删除关键表。
   - 检查 `backend/app/services/financial_statements_service.py` 是否能在不破坏现有 API 的前提下增加 `reporting_entity_id` 参数。

4. **利益相关者确认**：
   - 与业务/产品确认 Sub Legal 与 Reporting Entity 的边界是否符合审计实务。
   - 与技术团队确认 Entity 表扩展方案的可行性。

5. **最终验收**：
   - 所有新增/调整规格通过评审。
   - 代码影响清单明确，无高风险重构。
   - 形成从“原始设计 → 新方案概念 → 映射关系 → 实施顺序”的完整文档链。

---

## 6. 实施顺序建议

1. **Phase 1：补充概念规格**（`entity-legal-reporting-sub-alignment`、`unified-data-foundation-multi-view`）
2. **Phase 2：调整主规格**（`team-multi-ledger-management`、`financial-statements`、`ledger-register-project-concept-unification`）
3. **Phase 3：更新 Entity 和 Organization 模型**（数据库迁移、字段扩展）
4. **Phase 4：报表和权限层适配**（按 Reporting Entity 计算、跨 Ledger 聚合）
5. **Phase 5：测试与验证**（标准业务样例、合并报表、跨主体查询）

---

## 7. 结论

**建议：补充更清晰的方案，不推翻原方向。**

原始设计在主体分层和语义映射上已具备较好基础，新方案的价值在于用更贴近审计/财务实务的语言重新表述和组织这些概念。最佳路径是：
- 用新方案语言澄清原有概念边界；
- 将新方案概念映射到现有 `Entity`、`Organization`、`Ledger`、`AccountingUnit` 等模型；
- 通过补充规格和渐进式字段扩展实现落地；
- 避免直接重构 `ledger_id` 主边界和 Team 协作边界，防止记账闭环和审计闭环失稳。
