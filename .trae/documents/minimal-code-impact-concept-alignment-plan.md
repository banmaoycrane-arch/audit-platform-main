# 最小代码影响概念对齐计划

## 1. Summary（目标）

在保持现有代码结构、数据库表、API 参数、字段命名基本不变的前提下，通过**补充文档、增加注释、扩展少量辅助字段、保持向后兼容**的方式，让原有 `Team / Ledger / Project / Organization / Entity` 等概念与最新讨论的 `Organization / Legal Entity / Reporting Entity / Sub Legal` 三层模型、以及“统一数据底座 + 多视图分析”架构在语义上更清晰、更易维护。

核心原则：**代码能不变就不变，结果正常即可。**

---

## 2. Current State Analysis（当前状态）

### 2.1 已有探索结论

根据此前对 `.trae/documents/core-business-concepts-boundary.md`、`.trae/specs/entity-semantic-mapping/spec.md`、`.trae/specs/internal-accounting-unit/spec.md`、`.trae/specs/team-multi-ledger-management/spec.md`、`backend/app/db/models.py` 等文件的读取，当前系统已经具备以下能力：

- `Team`：用户协作与权限边界。
- `Ledger`：正式核算数据边界，所有凭证、期间、报表、审计数据以 `ledger_id` 为主过滤口径。
- `Project`：审计/工作任务边界，可关联多个 Ledger。
- `Organization`：历史兼容字段，部分旧表和业务逻辑仍使用，但已被核心治理文档弱化为非正式财务主边界。
- `Entity`：多维度主体语义映射实体，支持 `is_accounting_entity`、`is_legal_entity`、`is_tax_entity`、`is_management_entity` 标志。
- `EntityScope` / `VirtualEntitySet`：主体范围与虚拟集合，支持合并报表、集团范围、动态切换。
- `AccountingUnit`：内部核算单位（项目、部门、SKU、门店等）。

### 2.2 用户最新约束

用户明确要求：
1. **概念要更清晰**（用新方案语言重新表述）。
2. **代码层面尽量不要大面积重命名**。
3. **对后端只是让原来的定义与现在的定义更清晰**。
4. **代码能不变就不变**。
5. **尽量兼容处理**。
6. **只要结果正常即可**。

这意味着：不删除表、不改字段名、不改 API 路由参数名、不重构服务层核心逻辑，只在必要时做最小扩展或增加映射层。

---

## 3. Proposed Changes（建议改动）

### 3.1 总体策略

采用**“文档澄清 + 注释映射 + 最小字段扩展 + 兼容层”**四层策略：

1. **文档层**：新建概念映射文档，明确旧概念与新概念的对应关系。
2. **注释层**：在关键模型、服务、API 文件中增加中文注释，说明当前字段/参数在新概念体系中的含义。
3. **字段扩展层**：仅在确实需要区分的地方增加可选字段（如 `Entity` 增加 `legal_type` 枚举），不修改已有字段含义。
4. **兼容层**：保持现有 API 参数不变，新增可选参数时通过别名或默认值兼容旧调用。

### 3.2 文档层改动

#### 3.2.1 新增概念映射文档

- **文件**：`.trae/documents/legacy-to-new-concept-mapping.md`
- **内容**：
  - 用一张表说明旧代码概念 ↔ 新方案概念 ↔ 实务含义。
  - 明确 `Organization` 在新方案中作为“背景/关联方识别辅助”而不是顶层数据边界。
  - 明确 `Ledger` 在新方案中保持核算边界不变，是合同/发票/分录的承上启下维度。
  - 明确 `Entity` 在新方案中作为“可切换口径主体”，是 Legal 的不同口径重组。
  - 明确 `Project` 作为审计工作任务边界，与 Reporting Entity 的关系。
  - 明确 `Team` 作为使用者协作边界，与 Organization 作为被执行对象背景的区别。

#### 3.2.2 更新核心概念边界文档

- **文件**：`.trae/documents/core-business-concepts-boundary.md`
- **改动**：在现有表格中增加一列“新方案对应概念”，不修改原有定义，只增加映射说明。
  - 例如：
    - `Team` → 新方案：使用者协作组织（不变）
    - `Ledger` → 新方案：核算账簿 / 承上启下法律单据维度（不变）
    - `Organization` → 新方案：被执行对象背景 / 关联方识别辅助
    - `Entity` → 新方案：Legal 口径重组 / 可切换主体
    - `Project` → 新方案：审计工作任务边界 / 可关联多个 Reporting Entity

### 3.3 注释层改动

在以下文件的关键位置增加中文注释，说明新概念映射，但不改代码逻辑：

| 文件 | 注释内容 |
|---|---|
| `backend/app/models/team.py` | 说明 Team 是“使用者协作与权限边界”，不是被执行对象背景。 |
| `backend/app/models/ledger.py` | 说明 Ledger 是“核算边界 / 合同、发票、分录承上启下维度”，保持原有地位。 |
| `backend/app/models/project.py` | 说明 Project 是“审计工作任务边界”，可关联多个 Ledger/Reporting Entity。 |
| `backend/app/db/models.py`（Organization） | 说明 Organization 在新方案中是“被执行对象背景 / 关联方识别辅助”，不是数据过滤主边界。 |
| `backend/app/db/models.py`（Entity） | 说明 Entity 是“Legal 不同口径的重组 / 可切换主体”，用于会计/法律/纳税/管理多维度映射。 |
| `backend/app/db/models.py`（EntityScope / VirtualEntitySet） | 说明这是“Reporting Entity / 多视图分析”的技术实现载体。 |
| `backend/app/services/financial_statements_service.py` | 说明报表计算优先按 Ledger/Period，Organization 只是背景。 |

### 3.4 字段扩展层改动（最小）

#### 3.4.1 `Entity` 表增加 `legal_type` 字段（可选，默认 NULL）

- **目的**：在不破坏现有 `is_legal_entity` 等标志的前提下，给 Entity 增加一个更贴近新方案语义的分类标签。
- **字段**：`legal_type` VARCHAR(20)，可选值：`primary_legal`、`sub_legal`、`reporting_entity`、`accounting_unit`、`management_entity`。
- **默认值**：`NULL`，表示未分类，保持兼容。
- **影响**：现有代码无需修改，新功能可按需读取。
- **文件**：`backend/app/db/models.py`
- **迁移**：创建新的 Alembic 迁移，仅增加一列，无数据迁移逻辑。

#### 3.4.2 `Organization` 表可选扩展（如果业务需要）

- **字段**：`headquarters_entity_id`（可选）、`consolidation_scope`（可选 JSON）。
- **原则**：如果当前代码中 Organization 使用较少，可以暂不扩展；只在文档中说明其用途。
- **建议**：本次不改 `Organization` 表，避免任何数据库迁移风险。

### 3.5 兼容层改动

#### 3.5.1 报表 API 保持兼容

- 如果 `routes_reports.py` 已将参数改为 `ledger_id`，**保持当前状态**，因为这与新方案一致（Ledger 是核算边界）。
- 如果后续需要支持按 `reporting_entity_id` 或 `organization_id` 查询，采用**新增可选查询参数**的方式，不删除 `ledger_id` 参数。
- 例如：
  ```python
  @router.get("/trial-balance")
  def trial_balance(
      ledger_id: int,
      period_id: int,
      reporting_entity_id: int | None = None,  # 可选，用于多视图切换
      db: Session = Depends(get_db)
  ) -> dict:
      ...
  ```

#### 3.5.2 服务层保持兼容

- `financial_statements_service.py` 已改为按 `ledger_id` 过滤，这与新方案一致，保持当前实现。
- 如果后续需要按 Reporting Entity 聚合，通过 `VirtualEntitySet` 或 `EntityScope` 计算，不修改 `compute_account_balances` 核心签名。

#### 3.5.3 不改动的主要部分

| 模块 | 理由 |
|---|---|
| 表名 | 不改，避免数据库迁移和代码引用大面积改动。 |
| 字段名 | 不改，如 `organization_id`、`ledger_id`、`entity_id` 等保持不变。 |
| API 路由路径 | 不改，避免前端和外部集成变更。 |
| 服务层核心签名 | 尽量不改，已通过兼容参数实现扩展。 |
| `ledger_id` 主过滤口径 | 不改，保持核算边界稳定。 |
| `Team` 协作边界 | 不改，保持使用者权限模型稳定。 |

---

## 4. Assumptions & Decisions（假设与决策）

### 4.1 关键决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| 是否重命名表/字段？ | 否 | 避免大面积数据库迁移和代码改动。 |
| 是否新增独立 Legal Entity / Reporting Entity 表？ | 否 | 复用现有 `Entity` / `EntityScope` / `VirtualEntitySet` 表，通过字段扩展和文档映射实现。 |
| 是否修改 `ledger_id` 主过滤口径？ | 否 | Ledger 在新方案中保持核算边界不变。 |
| 是否修改报表 API 参数？ | 否 | 已通过改为 `ledger_id` 与新方案一致，保持现状。 |
| 是否立即实现多视图分析引擎？ | 否 | 本次只做概念澄清和最小字段扩展，多视图引擎作为后续独立规格。 |

### 4.2 假设

- 现有 `Entity` 表可以安全增加一个可选 `legal_type` 字段。
- 增加注释和文档不会引入运行时风险。
- 用户接受“概念更清晰但代码结构不变”的结果。

---

## 5. Verification Steps（验证步骤）

1. **文档验证**：
   - 检查 `.trae/documents/legacy-to-new-concept-mapping.md` 是否完整覆盖 Team / Ledger / Project / Organization / Entity / EntityScope / VirtualEntitySet / AccountingUnit。
   - 检查 `core-business-concepts-boundary.md` 新增的“新方案对应概念”列是否准确。

2. **代码注释验证**：
   - 抽查 `backend/app/models/team.py`、`backend/app/models/ledger.py`、`backend/app/models/project.py`、`backend/app/db/models.py` 中关键类/字段是否有新增中文注释说明新概念映射。

3. **数据库迁移验证**：
   - 创建 Alembic 迁移后，运行 `python -m alembic upgrade head` 和 `python -m alembic downgrade -1`，确认仅增加 `Entity.legal_type` 一列，无数据迁移逻辑。

4. **后端导入验证**：
   - 运行 `python -c "from app.main import app; print('OK')"`，确认无导入错误。

5. **前端构建验证**：
   - 运行 `pnpm run build:frontend`，确认无 TypeScript 错误。

6. **功能回归验证**：
   - 登录、账簿切换、凭证查询、报表查询、文件解析等关键功能正常。

7. **最终验收**：
   - 代码无大面积重命名。
   - 数据库表结构基本不变。
   - API 参数保持兼容。
   - 概念文档清晰可读。

---

## 6. 实施顺序

1. **Phase 1：文档与注释**（低风险，先完成）
   - 创建 `.trae/documents/legacy-to-new-concept-mapping.md`。
   - 更新 `.trae/documents/core-business-concepts-boundary.md`。
   - 在关键模型文件中增加中文注释。

2. **Phase 2：最小字段扩展**（低风险）
   - 在 `backend/app/db/models.py` 的 `Entity` 模型中增加 `legal_type` 字段。
   - 创建 Alembic 迁移，仅增加一列。

3. **Phase 3：验证**（无代码逻辑改动）
   - 运行后端导入测试。
   - 运行前端构建测试。
   - 运行 Alembic 迁移升降级测试。
   - 进行关键功能回归验证。

---

## 7. 结论

本计划采用**最小代码影响**策略：不推翻原方向、不大面积重命名、不改表结构，通过文档、注释和一个可选字段扩展，让原有概念与新方案在语义上对齐。最终目标是：**概念更清晰，代码更稳定，结果正常。**
