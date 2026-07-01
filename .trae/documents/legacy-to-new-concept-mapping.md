# 旧概念与新方案概念映射文档

> 本文档用于在**不修改代码结构和数据库表**的前提下，让原有 `Team / Ledger / Project / Organization / Entity` 等概念与最新讨论的 `Organization / Legal Entity / Reporting Entity / Sub Legal` 三层模型及“统一数据底座 + 多视图分析”架构在语义上更清晰、更易维护。
>
> 核心原则：**代码能不变就不变，通过映射澄清概念。**

---

## 一、映射总表

| 原有代码概念 | 新方案对应概念 | 实务含义 | 是否改变代码/表结构 |
|---|---|---|---|
| `Team` | **使用者协作组织** | 事务所/企业团队，负责成员权限、协作、项目管理 | 否 |
| `Ledger` | **核算账簿 / 法律单据承上启下维度** | 正式财务数据隔离边界；合同、发票、分录、审计测试都以 Ledger 为最小执行载体 | 否 |
| `Project` | **审计工作任务边界** | 审计/记账/税务/咨询项目，可关联多个 Ledger，用于任务分配、进度跟踪、底稿归档 | 否 |
| `Organization` | **被执行对象背景 / 关联方识别辅助** | 集团容器，用于识别内部关联法人，不直接作为数据过滤主边界 | 否 |
| `Entity` | **Legal 口径重组 / 可切换主体** | 会计主体、法律主体、纳税主体、管理主体的语义映射实体；可切换口径以适配不同场景 | 是（仅增加可选 `legal_type` 字段） |
| `EntityScope` | **主体范围（合并/税务/管理/法律）** | 动态定义一组主体范围，用于合并报表、多视图分析 | 否 |
| `VirtualEntitySet` | **Reporting Entity / 虚拟主体集合** | 如“XX集团”“合并范围”，支持多视图切换和合并抵消 | 否 |
| `AccountingUnit` | **业务单元 / 内部管理维度** | 项目、部门、产品线、门店、SKU 等，用于内部考核 | 否 |

---

## 二、分层定位详解

### 1. Team（使用者协作组织）

- **定位**：面向系统使用者的协作与权限边界。
- **使用场景**：
  - 事务所管理员创建团队，邀请会计师加入。
  - 分配团队角色、查看团队项目。
- **与 Organization 的关系**：
  - Team 是“谁在使用系统”。
  - Organization 是“系统处理哪个客户/集团对象”。
  - 一个 Team 可以服务多个 Organization，一个 Organization 可以被多个 Team 服务（如集团审计由多个团队协作）。
- **代码保持**：`backend/app/models/team.py` 不变，仅增加注释说明。

### 2. Ledger（核算账簿 / 法律单据承上启下维度）

- **定位**：正式财务数据隔离边界，是**业务执行的底层主维度**。
- **使用场景**：
  - 凭证、会计期间、期初余额、会计科目、审计发现、导入任务、源文件都以 `ledger_id` 为过滤条件。
  - 合同、发票、银行流水等法律单据也以 Ledger 为归属维度。
- **与 Legal Entity / Reporting Entity 的关系**：
  - Ledger 是 Legal Entity 或 Reporting Entity 下的具体核算账簿。
  - 一个 Legal Entity 可以有多个 Ledger（如不同年度、不同业务线）。
  - 一个 Reporting Entity 也可以有多个 Ledger（如内部管理需要多套账）。
- **代码保持**：`backend/app/models/ledger.py` 不变，仅增加注释说明。

### 3. Project（审计工作任务边界）

- **定位**：审计/记账/税务/咨询项目的工作范围。
- **使用场景**：
  - 项目承接、团队组建、任务分配、进度管理、质量控制、成果交付。
  - 可关联多个 Ledger，覆盖集团审计的多个子公司账簿。
- **与 Reporting Entity 的关系**：
  - Project 是工作任务边界，Reporting Entity 是核算主体范围。
  - 一个 Project 可以覆盖一个或多个 Reporting Entity。
- **代码保持**：`backend/app/models/project.py` 不变，仅增加注释说明。

### 4. Organization（被执行对象背景 / 关联方识别辅助）

- **定位**：集团容器，用于识别同一控制下的内部关联法人。
- **使用场景**：
  - 快速识别同集团内的内部关联方。
  - 合并报表范围定义。
  - 跨账簿汇总分析的辅助维度。
- **与 Team 的区别**：
  - Team 是使用者组织。
  - Organization 是被执行对象背景。
- **与数据过滤的关系**：
  - Organization **不是**数据过滤主边界，不能替代 `ledger_id`。
  - 只有在汇总分析、合并报表、关联方识别时才使用 Organization。
- **代码保持**：`backend/app/db/models.py` 中 `Organization` 表不变，仅增加注释说明。

### 5. Entity（Legal 口径重组 / 可切换主体）

- **定位**：多维度主体语义映射实体，是 Legal 实体在不同口径下的重组。
- **使用场景**：
  - 会计主体：用于核算和报表。
  - 法律主体：用于合同、税务、诉讼。
  - 纳税主体：用于税务申报。
  - 管理主体：用于内部考核。
- **与 Legal Entity 的关系**：
  - Legal Entity 是真实存在的法律/纳税实体。
  - Entity 是系统内部对这些实体的多口径映射，可以按不同场景切换口径。
- **代码变化**：在 `Entity` 表中增加可选 `legal_type` 字段，用于更清晰地标记实体类型（如 `primary_legal`、`sub_legal`、`reporting_entity` 等）。

### 6. EntityScope / VirtualEntitySet（Reporting Entity / 多视图分析载体）

- **定位**：动态主体范围和虚拟集合，用于支持多视图切换和合并报表。
- **使用场景**：
  - 定义合并报表范围。
  - 定义税务申报口径。
  - 定义管理考核口径。
  - 定义融资披露口径。
- **与 Reporting Entity 的关系**：
  - Reporting Entity 是报表主体概念。
  - EntityScope / VirtualEntitySet 是 Reporting Entity 在技术实现上的载体。
- **代码保持**：不变，仅增加注释说明。

### 7. AccountingUnit（业务单元 / 内部管理维度）

- **定位**：内部核算单位，用于项目、部门、产品线、门店、SKU 等管理维度。
- **使用场景**：
  - 成本中心、利润中心、项目核算。
  - 管理考核报表。
- **与 Reporting Entity 的区别**：
  - Reporting Entity 是会计核算主体/报表主体。
  - AccountingUnit 是 Reporting Entity 内部更细的管理维度。
- **代码保持**：不变，仅增加注释说明。

---

## 三、业务场景中的概念组合

### 场景 1：单体公司审计

| 层级 | 实例 |
|---|---|
| Organization | 客户集团（此时只有一个法人） |
| Primary Legal | 客户公司 |
| Ledger | 客户年度账簿 |
| Reporting Entity | 与客户公司对应 |
| Project | 2026年度财务报表审计项目 |

### 场景 2：集团合并审计

| 层级 | 实例 |
|---|---|
| Organization | 客户集团 |
| Primary Legal | 母公司、子公司 A、子公司 B |
| Sub Legal | 子公司 A 的分公司 |
| Ledger | 每个法人/分公司一套账簿 |
| Reporting Entity | 合并范围（VirtualEntitySet） |
| Project | 集团 2026 年度合并审计项目 |

### 场景 3：分公司审计

| 层级 | 实例 |
|---|---|
| Organization | 客户集团 |
| Primary Legal | 总公司 |
| Sub Legal | 北京分公司 |
| Ledger | 北京分公司账簿 |
| Reporting Entity | 北京分公司 |
| Project | 北京分公司专项审计项目 |

---

## 四、代码使用建议

### 1. 不要这样用

| 错误用法 | 原因 |
|---|---|
| 用 `organization_id` 过滤凭证/分录 | Organization 不是数据过滤主边界，会导致数据串扰。 |
| 用 `Team` 替代 `Organization` | 两者职责不同，Team 是使用者组织，Organization 是被执行对象背景。 |
| 用 `Reporting Entity` 作为合同签约主体 | 只有 Legal Entity / Sub Legal 具备工商签约资质。 |
| 用 `AccountingUnit` 出具法定报表 | AccountingUnit 是内部管理维度，不能替代 Reporting Entity。 |

### 2. 推荐这样用

| 场景 | 推荐维度 |
|---|---|
| 凭证/分录/期间/期初余额 | `ledger_id` |
| 合同/发票/银行流水/外部函证 | `ledger_id` + `legal_entity_id`（或从 Entity 映射） |
| 审计项目/任务分配 | `project_id` + `ledger_id` |
| 单体法定报表 | `ledger_id` |
| 合并报表/集团分析 | `organization_id` + `entity_scope_id` / `virtual_entity_set_id` |
| 内部管理报表 | `reporting_entity_id` / `accounting_unit_id` |
| 关联方识别 | `organization_id` + 人工关联方档案 |

---

## 五、与统一数据底座 + 多视图分析的关系

| 组件 | 原有实现 | 新方案理解 |
|---|---|---|
| 统一数据底座 | 原始业务数据（合同、发票、凭证、资金）按 `ledger_id` 存储 | 底层数据不变，仍然是 Ledger 级别的明细 |
| 口径规则引擎 | 通过 `EntityScope` / `VirtualEntitySet` 定义不同范围 | 新增税务/考核/融资三套规则参数，动态切换 |
| 多视图看板 | 按 Ledger、Organization、EntityScope 查询 | 一键切换：项目/法人/集团 + 税务/考核/融资 |
| 留痕层 | 操作日志 | 记录每次切换的口径、颗粒度、用户、时间 |

---

## 六、结论

- **代码保持不变**：Team、Ledger、Project、Organization、EntityScope、VirtualEntitySet、AccountingUnit 等表结构和字段名不变。
- **概念更清晰**：通过本文档和代码注释，明确每个概念在新方案中的定位和用法。
- **最小扩展**：仅在 `Entity` 表中增加可选的 `legal_type` 字段，用于标记 Primary Legal / Sub Legal / Reporting Entity 等类型。
- **结果正常**：所有现有功能继续按 `ledger_id` 主边界工作，新增概念映射不破坏已有逻辑。
