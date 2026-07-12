# Tag 与明细科目组合：设计目的、边界与动态配置

> **文档性质**：开发设计说明（非用户手册）  
> **版本**：1.0  
> **适用范围**：序时簿导入解析、维度中心、向量检索、三表勾稽  
> **相关实现**：`account_tag_resolution_service.py`、`account_tag_config.py`、`config/account_tag_rules.yaml`

---

## 1. 设计目的（Why）

本系统采用 **「一级科目（或强制保留的法定明细）+ Tag 维度」** 组合，而不是把 ERP 里的全部下级科目原样搬进科目表。

**核心目标不是「替企业改账」**，而是：

| 目标 | 说明 |
|------|------|
| **后期分析可检索** | 同一语义（客户、项目、费用类型、资产类别）跨科目、跨年度、跨 ERP 编码习惯，能用 Tag 聚合与向量相似度检索 |
| **技术识别更容易** | 科目编码保留报表/税法勾稽能力；Tag 承载管理口径与辅助核算，便于规则引擎与 LLM 补全 |
| **口径可切换** | 企业 A 把「项目」挂在 6602 下级，企业 B 挂在辅助核算——统一落到 `project` Tag，分析层一致 |
| **审计追溯不丢** | `original_code` / `original_name` / `source_sub_code` 保留导入原名，映射与留痕可还原 |

一句话：**科目管「法定与报表结构」，Tag 管「管理与分析语义」。**

---

## 1.1 设计底线（不可变）

以下原则是架构**核心**与**底线**，实现、文档、UI 文案均不得与之冲突；扩展 Tag、向量、自定义维度时亦不得突破。

### 底线 A：核算事实只在分录上

| 归属 `accounting_entries`（分录） | 归属 `entry_tags`（Tag） |
|----------------------------------|--------------------------|
| 借方/贷方金额 | 分析维度值（客户、部门、项目…） |
| 科目编码（`account_code` / `resolved_account_code`） | 分类（`category_id` / `category_code`） |
| 凭证号、日期、摘要、行号 | 规范名、权重、置信度、向量同步标记 |
| 借贷方向与平衡校验 | **不参与**借贷平衡 |

**Tag 通过 `entry_id` 关联分录，标注分录，不替代分录。**  
禁止把金额、正式科目、借贷方向迁入 Tag 或仅用 Tag 行表达一条会计事实。

代码真值：`AccountingEntry` ↔ `EntryTag`（1:N），见 `backend/app/db/models.py`。

### 底线 B：序时簿最小颗粒度是分录行，不是 `entities` 表

| 术语 | 表 | 角色 |
|------|-----|------|
| **分录 / Entry** | `accounting_entries` | 序时簿导入、入账、勾稽、分析的**最小财务事实单位**（一行） |
| **会计主体 / Entity** | `entities` | 组织、法人、scope 边界；**不是**序时簿逐行存储单位 |

原始业务数据 materialize 为 **`AccountingEntry`**；Tag 是挂在其上的多维标注，可随规则增加 category，但**不能**把最小颗粒度改成 `entities` 或其它表。

### 与「多 Tag 分析」的关系

- ✅ 同一分录可挂多个 **不同 category** 的 Tag（如 `expense_type` + `department` + 自定义维度）。
- ✅ Tag 可扩展、可映射、可换口径，便于分析。
- ❌ Tag 不得承担分录的核算职责；不得用 Tag 行代替分录行存储金额。

---

## 1.2 跨模块原则：Tag / 向量层平台开放 + 业务台账最小核心

固定资产、税务、进销存、合同、银行等**所有业务模块**共用同一套 **Tag + 向量语义层**（`TagCategory` / `EntryTag` / `DocumentTag` + Qdrant，`ledger_id` 隔离）。  
该层是**平台能力**，不是总账模块私有；新模块应优先复用，而不是各自建一套平行的「辅助核算表」。

### 原则 C：三层数据各守其位

```text
AccountingEntry（分录）     ← 最小财务事实：金额、科目、借贷（§1.1 底线）
       ↑ entry_id
EntryTag（分录 Tag）        ← 跨模块共享的分析/辅助核算语义 + 向量检索
       ↑ 映射 / 勾稽
Register（业务台账）        ← 各模块「独一份必须登记」的业务核心事实
DocumentTag（资料 Tag）     ← 原始证据侧语义（合同 PDF、发票影像等）
```

| 层 | 职责 | 典型内容 | 不做什么 |
|----|------|----------|----------|
| **分录** | 会计确认结果 | 借贷金额、`resolved_account_code` | 不承载模块专属业务单据全量字段 |
| **EntryTag** | 共享语义 / 辅助台账 | 部门、项目、资产类别/项目、客户、税种、自定义维度 | 不存金额、不替代分录 |
| **Register 核心** | 模块业务台账**最小必要**登记 | 资产卡片号、原值、启用日、折旧方法；发票代码号码；合同编号 | 不重复存已在 Tag/主数据里的分析字段 |
| **主数据 entity** | 高基数档案 | `counterparties`、`bank_accounts` | 见 §7.1 实体档案 |

### 原则 D：业务台账 ≈ 核心登记 + Tag 辅助

**业务台账（Register）**（固定资产卡片、发票台账、库存单、合同台账等）本质上是**业务事实台账**，与 Ledger（会计账簿）不同：

1. **可从分录 + Tag 转换/派生**（如 1601 分录 + `fixed_asset_class` / `fixed_asset_item` → 卡片草稿）。
2. **与分录存在映射关系**（`source_entry_id`、 capitalization 勾稽、折旧运行生成凭证等）。
3. **台账只保留「该模块独一份、必须登记」的核心字段**，避免与 Tag、主数据重复。
4. **其余管理/分析维度**（部门、项目、区域、费用类型、自定义口径等）→ **共用 EntryTag**，作为台账的**辅助台账层**（语义补充 + 向量检索），不在每个模块另建宽表。

口诀：

> **台账登核心，Tag 补语义；分录定金额，全模块共用向量。**

### 原则 E：避免后期「各模块另起炉灶」

| 反模式 | 推荐 |
|--------|------|
| 固定资产模块单独建「部门表、项目表、资产类别表」 | 类别/项目用共享 `TagCategory` + `EntryTag`；卡片表只留资产专属字段 |
| 税务模块重复维护客户名称库 | 复用 `counterparties` + `customer` Tag |
| 每模块独立向量库、独立标签字典 | 统一 `entry_tag_vector_service`，payload 带 `ledger_id` + `category_code` |
| 台账存金额以替代总账 | 金额仍以分录为准；台账金额与分录勾稽、差异入待处理 |

**信息在账簿内高度共享**：同一 `customer` Tag 可同时服务往来函证、收入分析、发票匹配、合同台账；同一 `fixed_asset_item` Tag 可串联 1601 分录、资产卡片、折旧计划。

### 典型链路：固定资产卡片账

```text
序时簿导入
  → 分录 1601 + Tag(fixed_asset_class, fixed_asset_item)   【共享 Tag 层】
  → 规则/人工确认 → 生成/关联 固定资产卡片（Register 核心） 【卡片号、原值、启用日、折旧方法…】
  → 卡片上不重复存部门/项目 → 从关联分录 EntryTag 读取          【Tag 辅助层】
  → 折旧计提 → 生成 1602/6602 分录（仍回 §1.1 底线）           【分录层】
```

税务、库存等模块同理：发票/单据号、税率、商品行等进 Register 核心；往来、项目、业务线进共享 Tag。

**固定资产模块**：

- **决策记录（v1.0 开发起点）**：[fixed-asset-v1-decision-record.md](./fixed-asset-v1-decision-record.md)
- **表结构草案**（全生命周期）：[fixed-asset-register-schema-draft.md](./fixed-asset-register-schema-draft.md) §2.1

### 与 DocumentTag 的分工

- **DocumentTag**：证据文件上的语义（尚未或尚未完全入账）。
- **EntryTag**：已 materialize 到分录的语义（全模块分析主通道）。
- **Register**：模块业务对象生命周期（状态、专属编号、与分录/证据的链接）。

证据 → 台账 → 分录 → Tag 向量，四层可互相映射，但**不重复存同义字段**。

### 新模块接入检查清单

- [ ] 是否复用 `TagCategory` / `EntryTag`，而非新建平行标签体系？
- [ ] Register 表是否只含「该模块独一份必须登记」字段？
- [ ] 分析维度是否走共享 Tag + 向量，而非台账宽表？
- [ ] 与分录的映射（生成/勾稽）是否明确，且金额仍以 `AccountingEntry` 为准？
- [ ] 是否违反 §1.1（Tag/台账不替代分录存借贷金额）？

---

## 2. 工作中边界为何不清晰

实务里「明细科目 vs 辅助核算 / Tag」往往混在一起，原因包括：

1. **ERP 习惯不同**：有的企业把客户做到 `1122.01.001`，有的只做 `1122` + 辅助项「客户」。
2. **行业差异**：制造业常见「料工费」明细；贸易业更偏往来与渠道；同一一级科目下结构完全不同。
3. **历史沿革**：合并、换系统、手工改科目，会出现「名称像 Tag、编码像明细」的混合形态。
4. **管理口径迭代**：今年按部门考核，明年按项目——静态科目表改不动，Tag 更合适。
5. **准则/税法硬边界**：应交增值税明细、应付职工薪酬明细、权益类明细等 **必须保留层级**，不能为了分析方便扁平化。

因此：**不能写死一套全国统一的「二级=Tag、三级=明细」规则**；需要 **默认启发式 + 账簿级可覆盖 + 导入后人工确认**。

---

## 3. 决策框架：什么时候用明细科目，什么时候用 Tag

### 3.1 三条硬规则（优先于企业管理习惯）

```
1. 税法 / 准则 / 三表勾稽需要的 → 保留明细科目层级（mandatory_hierarchical）
2. 仅用于管理分析、口径切换、尽调检索的 → 优先 Tag
3. 拿不准时 → 保留原始段（original_*），解析时先 Tag 化，维度中心可改映射策略后重算
```

### 3.2 简易判断表（给实施与审阅人员）

| 问题 | 倾向 | 示例 |
|------|------|------|
| 删掉这层会不会影响增值税申报、职工薪酬计提、权益变动表？ | **保留明细** | `2221.01.07` 进项税额转出、`2211.01.01` 工资、`4101` 盈余公积下级 |
| 是否只在内部管理报表里用，准则并不要求单独科目？ | **转 Tag** | 部门、项目、区域、费用类型（在 6601/6602 下） |
| 值是否高基数、需做主数据维护（户名、统一社会信用代码）？ | **Tag + 主数据** | 银行 `bank_account`、客户 `customer` |
| 值是否低基数、枚举型、常变？ | **Tag（text/enum）** | 费用类型「差旅费」、资产类别「房屋建筑物」 |
| 名称是否天然两段式（类别 + 实例）？ | **一级科目 + 双 Tag** | 固定资产 `1601` → `fixed_asset_class` + `fixed_asset_item` |
| 企业坚持把某管理维度做到科目下级且需与总账逐行一致？ | **保留明细**（账簿 override 加入 mandatory 列表） | 某集团强制 `6602.01` 行政部费用单独科目 |

### 3.3 口诀（产品内可展示 shortened 版）

> **法定明细不能动，管理维度用 Tag；原名永远留痕，账簿策略可调整。**

---

## 4. 动态配置：不能静态，如何落地

### 4.1 已有机制（代码真值）

配置优先级（高 → 低）：

```
账簿 LedgerSettings.account_tag_rules_override
    ↓ 合并覆盖
数据库 GlobalSettings（account_tag_rules）
    ↓
backend/config/account_tag_rules.yaml
    ↓
account_tag_config._default_config() 内置兜底
```

关键字段：

| 配置项 | 作用 |
|--------|------|
| `mandatory_hierarchical_accounts` | 强制保留完整编码，**不**转 Tag |
| `mandatory_hierarchical_keywords` | 科目名称关键词兜底保留 |
| `account_code_tag_category` | 某一级科目下，下级段默认映射到哪个 Tag 分类 |
| `account_name_tag_category` | 科目名称关键词 → Tag 分类 |
| `auxiliary_keywords` | 摘要/名称补充识别（部门、项目、区域等） |

账簿级覆盖 API / 服务：`load_ledger_account_tag_override`、`save_ledger_account_tag_override`（见 `account_tag_config.py`）。

**外部映射规则**（`TagMappingRule`）：ERP 编码 / 摘要 / 自由标签 → 内部 TagCategory，与解析映射互补，适合「对接旧系统」而非替代 mandatory 规则。

### 4.2 推荐动态策略（简易 + 可演进）

#### 阶段 A：导入前（维度中心 · 解析映射）

- 审阅平台默认 YAML + 展示本账簿 override diff。
- 企业特殊科目：仅追加 `mandatory_hierarchical_accounts` 或改 `account_code_tag_category`，**不要改代码**。
- 确认后写入 `tag_rules_reviewed_at`（门禁：结构化导入前必须确认）。

#### 阶段 B：导入中（自动解析）

- `account_tag_resolution_service` 按合并后配置拆分。
- 输出：`resolved_account_code` + `entry_tags_payload` + `original_row` 追溯字段。
- 模糊段标记 `requires_llm_resolution`，不阻塞全批。

#### 阶段 C：导入后（待处理队列 / Step4）

- 简称、主数据缺口、映射留痕——**人工修正 display_name，不动科目结构**。
- 若发现整类科目都应保留明细：回到维度中心改 override，**重跑 staging 解析**（或下一批导入生效）。

#### 阶段 D：分析期（向量 + SQL）

- SQL 聚合：`(ledger_id, account_code, category_code, tag_value)`  btree 索引。
- 向量：Tag 文本 + 摘要；`ledger_id` 隔离 collection。
- 明细科目用于报表勾稽查询；Tag 用于跨科目语义检索——**各走各的索引，不混在一个宽表里扫全表**。

### 4.3 不建议的做法

| 做法 | 问题 |
|------|------|
| 全部扁平化为 Tag | 增值税、薪酬、权益勾稽失效 |
| 全部保留 ERP 明细 | 向量与跨科目分析退化，编码习惯锁死 |
| 每家企业一套硬编码 Python | 运维成本高，与「动态 override」重复 |
| 运行时每条分录查 DB 规则树 | 性能差；应 **导入时 materialize 到 staging/entry** |

---

## 5. 性能边界：便于使用且不影响性能

### 5.1 原则：**解析时决定，查询时只读**

| 阶段 | 做什么 | 性能要点 |
|------|--------|----------|
| 导入解析 | 读配置一次 → 拆分科目/Tag → 写入 staging | O(行数 × 规则数)，规则列表按 priority 排序后 **早停匹配** |
| 确认入账 | staging → 正式分录 + EntryTag | 批量 insert，category 预先 `_ensure_tag_categories` |
| 向量同步 | 异步 `vector_pending` 队列 | 按 ledger 批量 upsert，不阻塞入账 |
| 分析查询 | 按 `ledger_id` + `account_code` + Tag 过滤 | 依赖 DB 索引与 Qdrant payload filter，**不在查询阶段重跑解析** |

### 5.2 规则规模建议

| 类型 | 建议上限（单账簿） | 说明 |
|------|-------------------|------|
| mandatory 明细列表 | 200 项内 | 仅法定 + 企业强制保留 |
| account_code → category 映射 | 50 项内 | 一级科目有限 |
| TagMappingRule | 500 项内 | 外部 ERP 对接；可禁用不删 |
| auxiliary_keywords | 每类 30 词内 | 摘要匹配，过长则误匹配与 CPU 上升 |

超出时：合并正则规则、提高 priority 分层、把冷门映射移到「导入后批处理」而非逐行正则。

### 5.3 缓存建议（已实现或可加强）

- `load_account_tag_config(db, ledger_id)`：请求级 / 导入 job 级缓存合并结果。
- `TagCategory`：按 `ledger_id` 一次加载为 dict，解析循环内 O(1) 查找。
- 向量：仅同步 `name_standardized=true` 或业务确认后的 Tag，减少无效 embedding。

---

## 6. 典型场景示例

### 6.1 银行存款：一级 + Tag（账户明细）

- 科目：`1002`（保留）
- Tag：`bank_account` + `source_sub_code` + 规范户名
- 原因：货币资金审计要账户级明细，但不需要 `1002.01.02.03` 无限扩张科目表

### 6.2 应交增值税：全层级保留

- 科目：`2221.01.07`（保留，不转 Tag）
- 原因：申报表行次与明细一一对应

### 6.3 固定资产：一级 + 双 Tag

- 科目：`1601`
- Tag：`fixed_asset_class`（房屋建筑物）+ `fixed_asset_item`（堆场及封闭棚）
- 原因：类别可聚合，实例可向量检索；避免 `1601.01.001.002` 爆炸

### 6.4 其他应付款 - 个人：一级 + Tag

- 科目：`2241`
- Tag：`counterparty_object` = 张悦
- 原因：自然人姓名不是法定明细科目；主数据可维护、可映射留痕

### 6.5 某企业强制「部门费用科目」：override 保留明细

- 在 `account_tag_rules_override.mandatory_hierarchical_accounts` 增加 `6602.01`、`6602.02`…
- 该账簿导入时不再把部门段抽成 Tag
- 其他企业默认仍用 `department` Tag

---

## 7. 与产品界面的对应

| 界面 | 职责 |
|------|------|
| 维度分类 | 定义 Tag 字典（category） |
| 标签映射 / 解析映射 | 编辑账簿级 `account_tag_rules_override` |
| 外部映射 | ERP 外来编码 → TagCategory（兼容层） |
| 维度值主数据 | Tag 值的主数据，**按科目性质分粒度**（见下表） |
| 待处理队列 | 导入后修正名称、补主数据、查看映射留痕 |
| Step4 凭证复核 | 行级确认 Tag 与规范全称 |

### 6.1 主数据收集粒度（维度值主数据页）

**原则**：Tag 替代的是「辅助核算挂在哪」这一层结构，**不是**削减语义信息，也**不是**把管理维度降级成「只能向量检索的注释」。

系统把维度值维护分成 **三类**（与 `dimensionUtils.resolveMasterDataCollectionKind()` 一致）：

| 类型 | 适用分类 | 存储位置 | 维护方式 | 设计意图 |
|------|----------|----------|----------|----------|
| **实体档案** | `bank_account`（1001/1002）、`customer` / `supplier` / `counterparty_object` | `bank_accounts` / `counterparties` | 维度值主数据页补登记；字段尽量齐全 | 对应原辅助核算档案（户名、信用代码、关联方等） |
| **共享 Tag** | `department`、`project`、`expense_type`、`fixed_asset_*`、`product` / `service`、自定义 text 分类等 | **`entry_tags`（EntryTag）** | 导入时自动解析沉淀；待处理队列 / Step4 补规范名；**不要求**独立模块表 | **替代大量辅助核算项**；费用、资产、项目等子模块**共用同一套 Tag**，避免「每模块一张主数据表」 |
| **法定明细** | mandatory 列表内科目 | 科目表层级 | 保留 ERP 下级编码 | 增值税、薪酬、权益等勾稽 |

#### 共享 Tag ≠「无补登记」

过去界面文案「向量 Tag、无补登记」**不准确**，容易误解为这类维度不重要。正确理解：

- **有维护**：简称 → 规范名、映射留痕、Step4 人工确认；必要时写入向量库做语义检索。
- **无独立档案表**：不像往来单位那样强制走 `counterparties` 登记表单；值随分录进入 `EntryTag`，全账簿、全模块可聚合查询。
- **向量化是能力之一**：共享 Tag 同步 Qdrant 是为了尽调检索与相似匹配，**不是**其唯一存在理由。

#### 同一分录可多 Tag + 自定义细分

一条分录可同时携带多个 Tag，例如：

```
科目 6602 管理费用
  ├─ expense_type = 差旅费
  ├─ department   = 行政部
  └─ business_line = 华东区        ← 账簿自定义分类
```

实现真值：`account_tag_resolution_service` 的 `suggested_tags` 为**列表**；固定资产等为**双 Tag**（class + item）。  
企业可在「维度分类」新建任意 `snake_case` 分类，在「解析映射 / 外部映射」中引用；**规则配好后**即可：

- 把 ERP 下级段映射到不同 category；
- 跨年、跨 ERP 统一到同一 Tag 口径做分析；
- 在不改科目表的前提下**继续细分**管理粒度。

#### 与 engine-architecture 的对应

- `TagCategory`：分类字典（可树形、可自定义）。
- `EntryTag`：分录上的 Tag 实例（`category_id` + `tag_value` + `display_name` + 可选 `value_id` 链实体档案）。
- `TagMappingRule`：外部编码 → 内部分类（口径转换兼容层）。
- `account_tag_rules_override`：账簿级「某科目下级段 → 哪个 category」。

前端实现：`dimensionUtils.resolveMasterDataCollectionKind()` + `DimensionValuesPanel` 按行判断；共享 Tag 在本批使用层显示「已规范 / 待规范名」，而非误标为「无需维护」。

---

## 8. 开发检查清单

**新增科目解析规则时：**

- [ ] 是否影响法定勾稽？→ 加入 mandatory 而非 Tag
- [ ] 是否仅管理口径？→ Tag + category 映射
- [ ] 是否需账簿差异？→ override 字段，而非改全局 YAML
- [ ] 是否保留 `original_*` 与映射留痕？
- [ ] 是否避免在查询路径调用 `resolve_account_tags`？

**新增 Tag 分类时：**

- [ ] 是否违反 §1.1 底线（Tag 不承载金额/科目/借贷；最小颗粒度仍为分录）？
- [ ] `value_type` / `source_table` 是否与主数据一致（entity → 档案表；text → 共享 EntryTag）
- [ ] 是否需与现有分类组合（双 Tag：class + item；或多 Tag 并存）
- [ ] 自定义分类是否已在解析映射 / 外部映射中可引用
- [ ] 待处理队列是否需特殊文案（如人名、仅姓氏）

---

## 9. 后续演进（可选，非当前阻塞）

1. **解析映射 UI 可视化 diff**：YAML 默认 vs 账簿 override  side-by-side。
2. **规则影响预览**：上传序时簿样本 100 行，预览「保留明细 / 转 Tag」比例。
3. **TagMappingRule 预设种子**：从 `account_tag_rules.yaml` 自动生成常见外部映射，减少空表（见维度中心「外部映射」）。
4. **按期间策略**：同一账簿不同年度 override 版本（需 LedgerSettings 版本化，复杂度高，慎做）。

---

## 10. 参考代码索引

| 模块 | 路径 |
|------|------|
| 科目拆分与 Tag 建议 | `backend/app/services/doc_parsing/account_tag_resolution_service.py` |
| 配置加载与账簿覆盖 | `backend/app/config/account_tag_config.py` |
| 默认规则 YAML | `backend/config/account_tag_rules.yaml` |
| 维度就绪门禁 | `backend/app/services/doc_parsing/dimension_readiness_service.py` |
| 外部映射 CRUD | `backend/app/services/doc_parsing/tag_mapping_rule_service.py` |
| 向量 ledger 隔离 | `backend/app/services/...`（EntryTag 同步与 search 带 `ledger_id`） |

---

**维护说明**：企业实践或准则解释变更时，优先更新 **账簿 override** 与本文件 §3、§6 示例；仅当默认值对大多数客户不适用时，才修改 `account_tag_rules.yaml`。
