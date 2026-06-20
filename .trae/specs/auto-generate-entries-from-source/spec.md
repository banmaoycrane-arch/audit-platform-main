# 原始资料自动生成分录规则化 + 基础科目治理 Spec

## Why

当前记账模式 Step3 「自动生成会计分录」存在多处不规范：

- 会计期间未体现（凭证日期硬编码 `2024-01-15`）
- 凭证字号未遵循「银/转/收/付/记/工」规则（任何业务都标 `记-001`）
- 摘要随机生成，未根据合同/发票/银行回单动态产生
- 对方单位字段语义混乱（既写客户又写"税务局"），缺规划

**进一步暴露的根因问题：**

1. 系统缺乏基础资料模块——会计科目表无 CRUD 与作废、缺少遵循《企业会计准则》的默认跨级科目库；
2. 对方单位字段没有清晰规划，与"客户档案/供应商档案/关联方"概念混用；
3. 辅助核算（部门、项目、人员、产品、渠道等）应当扁平化为 **Tag**，同时存到关系数据库（强一致结构）和向量数据库（语义检索），而不是再造二级辅助核算。

## What Changes

### A. 基础资料：会计科目治理

- 新增模型 `ChartOfAccounts`（会计科目表）：
  - `code`（科目代码，4–8 位）
  - `name`（科目名称）
  - `parent_code`（父科目代码，预留扩展，但默认科目均为一级）
  - `level`（默认 1；**默认科目库只预置一级**）
  - `category`（资产/负债/共同/所有者权益/成本/损益）
  - `direction`（借/贷）
  - `is_terminal`（是否末级；一级也是末级）
  - `status`（active/disabled/archived）
  - `is_system`（是否准则默认科目，禁删只可禁用）
- **设计规则**：默认科目库 SHALL 仅预置一级科目；常见的二级（如「应交税费-应交增值税-销项/进项税额」「应付职工薪酬-工资/社保」「主营业务收入-XX 产品」）一律由 `EntryTag` 表达，不再下挂二级科目。
- 新增 API：
  - `GET /api/coa`（列表 + 树）
  - `POST /api/coa`（新增）
  - `PUT /api/coa/{code}`（修改）
  - `POST /api/coa/{code}/disable`（停用）
  - `POST /api/coa/{code}/archive`（作废/归档）
  - `DELETE /api/coa/{code}`（删除，仅限非系统、无业务引用）

### B. 对方单位重新规划

- 对方单位 = `Counterparty`，独立基础档案，不再是分录里的自由文本。
- 新增模型 `Counterparty`：
  - `id`、`name`、`role`（customer/supplier/related_party/government/individual/internal/other）
  - `unified_credit_no`（统一社会信用代码）
  - `is_related_party`（是否关联方，链接 `Entity` 体系）
  - `default_entity_id`（默认关联到的 [Entity](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/db/models.py)，可空）
  - `is_active`
- `accounting_entries.counterparty`（旧字段保留兼容）改为也支持 `counterparty_id`（FK，可空），保持向后兼容。
- 在自动生成分录时：
  - 借方记账：`counterparty` = 资金/物流/服务的来源方
  - 贷方记账：`counterparty` = 资金/物流/服务的去向方
  - 多行凭证不跨行复制
  - 税费行不再硬编码"税务局"，留空或写为系统级 `counterparty_role=government` 的统一档案
  - 原始证据未提供时留空
- 新增 API：
  - `GET /api/counterparties`
  - `POST /api/counterparties`
  - `PUT /api/counterparties/{id}`
  - `POST /api/counterparties/{id}/disable`

### C. 辅助核算转 Tag（双库存储）

- 取消"二级辅助核算"概念（部门、项目、人员、产品等不再以二级科目存在）。
- 新增模型 `EntryTag`（分录标签）：
  - `entry_id`（FK accounting_entries）
  - `tag_type`（dept/project/employee/product/sku/channel/customer/supplier/region/business_line/free_form）
  - `tag_value`（字符串值或外键键）
  - `tag_value_normalized`（归一化后的值，便于精确匹配）
  - `confidence`、`source`（manual/ai/rule）
  - `created_at`
- 双库存储：
  - **关系数据库** `entry_tags` 表（结构化、可联接查询）
  - **向量数据库** Qdrant 同步写入 `entry_tag_embeddings` 集合（携带 `entry_id`、`tag_type`、`tag_value` payload，便于语义检索）
- 自动生成分录时：从摘要、对方单位、原始证据中提取候选 tag 并双库写入。
- 新增 API：
  - `GET /api/entries/{id}/tags`
  - `POST /api/entries/{id}/tags`
  - `DELETE /api/entries/{id}/tags/{tag_id}`
  - `POST /api/entries/tags/search`（按 tag_type/value/语义搜索）

### D. 自动生成分录引擎规则化

- 新增服务 `entry_generation_service.py`：
  - 入参：`job_id`、`period_id`
  - 步骤：
    1. 读取该 job 已解析的合同、发票、银行回单、入库单
    2. 按业务循环聚合（合同 → 入库 → 发票 → 收款）
    3. 选择匹配的科目（来自科目库），生成借贷
    4. 凭证字按规则推荐：
       - 银行回单 → `银`
       - 现金借 → `收`、现金贷 → `付`
       - 工资 → `工`
       - 计提/折旧/内部转账 → `转`
       - 其他 → `记`
    5. 凭证日期落在所选会计期间内（越界自动夹紧并打 `date_clamped=true`）
    6. 摘要使用 [summary_template_service](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/services/summary_template_service.py) 拼装
    7. 对方单位按上面 B 规则填写
    8. 提取 tag 候选写入 EntryTag（草稿阶段先内存暂存）
- 新增 API：
  - `POST /api/import-jobs/{job_id}/generate-entries`（返回草稿，不落库）
  - `POST /api/import-jobs/{job_id}/commit-entries`（落库 + 写 tag + 写向量）

### E. 前端

- 新增基础资料页面 `BasicData/ChartOfAccountsPage.tsx`（会计科目 CRUD + 树状展示）
- 新增基础资料页面 `BasicData/CounterpartiesPage.tsx`（对方单位 CRUD）
- 修改 [Step2ImportSource.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/AccountingMode/Step2ImportSource.tsx)：让用户选择或创建会计期间，把 `periodId` 通过 URL 带到 Step3
- 修改 [Step3GenerateEntries.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/AccountingMode/Step3GenerateEntries.tsx)：去 mock，调用 `generate-entries`，复核后再 `commit-entries`，列表展示真实凭证字号、对方单位、tag

## Impact

- 受影响 specs：
  - `summary-library`：摘要模板真正接入生成流程
  - `accounting-period-snapshot`：自动生成的分录与会计期间对齐
  - `entry-line-number`：草稿落库时使用既有连续行号规则
  - `adaptive-import-engine`：解析字段成为生成分录的输入
  - `entity-semantic-mapping`：对方单位通过主体语义识别归一化
  - `internal-accounting-unit`：辅助核算转 tag 取代二级辅助核算
- 受影响代码：
  - 后端：`db/models.py`、`services/entry_generation_service.py`、`services/coa_service.py`、`services/counterparty_service.py`、`services/entry_tag_service.py`、`api/routes_coa.py`、`api/routes_counterparties.py`、`api/routes_entry_generation.py`、`api/routes_entry_tags.py`、`main.py`
  - 前端：`pages/BasicData/ChartOfAccountsPage.tsx`、`pages/BasicData/CounterpartiesPage.tsx`、`pages/AccountingMode/Step2ImportSource.tsx`、`pages/AccountingMode/Step3GenerateEntries.tsx`、`api/client.ts`

## ADDED Requirements

### Requirement: 会计科目 CRUD 与默认科目库

系统 SHALL 提供会计科目的新增/修改/停用/作废/删除接口，并预置《企业会计准则》默认跨级科目（一级 + 常用二级）。

#### Scenario: 系统科目不可硬删

- **WHEN** 用户尝试删除 `is_system=true` 的科目
- **THEN** 返回 400，提示「准则默认科目不可删除，可停用」

#### Scenario: 已被使用的自定义科目不可硬删

- **WHEN** 自定义科目被任意 `accounting_entries` 引用
- **THEN** 返回 400，提示「该科目存在业务记录，不可删除」

### Requirement: 对方单位独立档案 + 角色

系统 SHALL 把对方单位提升为独立档案 `Counterparty`，分录通过 `counterparty_id` 关联。原始证据未提供时分录的对方单位 SHALL 留空。

#### Scenario: 税费行不再硬编码"税务局"

- **GIVEN** 销售业务自动拆分销项税
- **WHEN** 生成「应交税费-应交增值税-销项税额」行
- **THEN** 该行 `counterparty_id` 留空或链接到角色为 `government` 的系统档案

### Requirement: 辅助核算转 Tag（双库存储）

系统 SHALL 把部门/项目/人员/产品/渠道/客户/供应商/区域/业务线等辅助核算统一改为 `EntryTag`，并同步写入关系数据库与向量数据库。

#### Scenario: 写库即写向量

- **WHEN** 自动生成分录提取出 tag
- **AND** `commit-entries` 调用成功
- **THEN** `entry_tags` 表新增对应记录
- **AND** Qdrant `entry_tag_embeddings` 集合同步写入对应向量
- **AND** 当 Qdrant 不可用时，关系库写入仍成功，向量写入降级为待重试

### Requirement: 自动生成分录与会计期间联动

系统 SHALL 接收 `period_id` 作为生成草稿分录的必填上下文，并把所有草稿分录的 `voucher_date` 限制在该期间的 `[period_start, period_end]` 之内。

#### Scenario: 缺少 period_id

- **WHEN** 调用 `POST /api/import-jobs/{id}/generate-entries` 未带 `period_id`
- **THEN** 返回 400 且 detail 提示「缺少会计期间」

### Requirement: 凭证字与业务类型一致

系统 SHALL 按以下优先级推荐凭证字：

1. 银行回单/银行流水 → 银字
2. 现金借方 → 收字；现金贷方 → 付字
3. 摘要含工资/薪酬 → 工字
4. 计提/折旧/摊销/内部转账 → 转字
5. 默认 → 记字

#### Scenario: 银行回单生成银字

- **WHEN** 原始资料中存在银行回单且本笔涉及银行存款科目
- **THEN** 草稿分录 `voucher_no` 以 `银-` 为前缀

### Requirement: 摘要根据原始证据动态生成

系统 SHALL 调用 [summary_template_service](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/services/summary_template_service.py)，以「凭证字 + 主科目 + 对方单位 + 业务关键词」拼装摘要。

#### Scenario: 收到客户货款的银字摘要

- **GIVEN** 银行回单显示来款方 `A公司` 金额 `116000`
- **THEN** 摘要形如「收到 A公司 货款」，不再随机文本

### Requirement: 草稿与落库分离

系统 SHALL 提供 `generate-entries`（草稿，不入库）与 `commit-entries`（真实落库 + 写 tag + 写向量）两步。

## MODIFIED Requirements

### Requirement: 记账模式 Step3 「生成凭证」

不再使用 mock。Step3 SHALL 通过 `?jobId=&periodId=` 上下文调用真实 API 拉取草稿；用户复核后调用 `commit-entries` 落库。

### Requirement: 记账模式 Step2

Step2 SHALL 在上传文件之外，必须让用户选择或创建会计期间，并把 `periodId` 通过 URL 传给 Step3。

### Requirement: 内部核算单位

Tag 体系 SHALL 取代旧的「二级辅助核算」实现，但仍兼容原 [internal-accounting-unit](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/internal-accounting-unit) 的颗粒度建模。

## REMOVED Requirements

无。
