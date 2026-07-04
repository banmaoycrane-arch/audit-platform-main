# 审计模式「导入序时簿模式」Spec

## Why

审计师从被审计单位获取的关键审计证据之一是「序时簿（day book）」——按日期顺序、连续登记的全部凭证流水。当前审计模式 Step3 已支持「凭证导入」和「序时簿导入」两个 UI Tab（`dashboard-home-and-day-book-import` spec 已完成），但两者在后端处理逻辑上完全复用凭证导入流程，没有真正区分序时簿的语义。

在审计实务中，序时簿与凭证导入有本质区别：
- **凭证导入**：被审计单位已整理好的凭证文件，通常包含凭证号、日期、科目、借贷金额等
- **序时簿导入**：按日期顺序连续登记的原始流水，可能包含大量未整理的分录，需要系统按凭证号分组、识别完整性、检测跳号

因此需要：
1. 后端真正区分 `source_type=audit_day_book`，在导入时执行序时簿特有的处理逻辑（按凭证号分组、完整性校验、跳号检测）
2. 前端在导入时传递 `source_type` 参数，让后端知道当前导入的是序时簿
3. 序时簿导入完成后，提供序时簿特有的审计视图（如按日期排序、凭证号连续性检测、跳号提示）

## What Changes

- 后端修改：
  - `ImportJob.source_type` 字段已存在，当前默认 `voucher_import`。需要让 `routes_imports.py` 在创建导入任务时支持传入 `source_type`
  - `import_service.py` 的 `process_import_job` 函数增加对 `source_type=audit_day_book` 的分支处理：
    - 按 `voucher_no` 分组，将同一凭证号的多行分录合并为一个凭证
    - 执行完整性校验：检测凭证号是否连续、是否有缺失
    - 生成跳号检测报告
  - 新增 `audit_day_book_service.py`：序时簿专用处理逻辑
- 前端修改：
  - `Step3ImportEntries.tsx` 在调用 `api.createImportJob` 时传入 `source_type` 参数（当前 Step2 创建 job 时未传）
  - 序时簿 Tab 导入完成后，展示序时簿特有的检测信息（跳号、完整性）
- 新增 API：
  - `GET /api/import-jobs/{job_id}/day-book-report`：获取序时簿导入的检测报告（跳号、完整性）
- 新增测试：
  - `test_audit_day_book_api.py`：覆盖序时簿导入、检测报告

## Impact

- 影响的 specs：
  - `dashboard-home-and-day-book-import`：序时簿 UI 入口已存在，本 spec 补齐后端语义
  - `audit-step3-real-entries`：Step3 已接入真实分录，本 spec 增加序时簿模式
  - `adaptive-import-engine`：复用自适应导入引擎，增加序时簿模板识别
- 影响的代码：
  - 后端：`routes_imports.py`、`import_service.py`、新增 `audit_day_book_service.py`
  - 前端：`Step3ImportEntries.tsx`、`client.ts`
  - 测试：新增 `test_audit_day_book_api.py`

## ADDED Requirements

### Requirement: 序时簿导入模式

系统 SHALL 支持审计模式下的序时簿导入，与凭证导入在语义和处理逻辑上区分。

### Requirement: 科目层级解析与Tag生成

系统 SHALL 对导入的科目编码/名称进行解析，按"一级科目保留、强制二级科目保留、其余下级段转Tag"原则处理。

#### Scenario: 一级科目保留

- **WHEN** 导入科目编码为4位（如"1002银行存款"）
- **THEN** `resolved_account_code` 和 `resolved_account_name` 保留原值

#### Scenario: 强制二级科目保留完整层级

- **WHEN** 导入科目属于税法/会计准则强制要求的二级科目（如"2221.01.01应交税费-应交增值税-进项税额"）
- **THEN** `resolved_account_code` 和 `resolved_account_name` 保留完整层级编码和名称
- **AND** 不生成 EntryTag

#### Scenario: 辅助核算维度转EntryTag

- **WHEN** 导入科目存在下级段（如"1122.01应收账款-A客户"、"6001.01主营业务收入-产品X"）
- **THEN** `resolved_account_code` 取一级科目（如"1122"、"6001"）
- **AND** 根据科目类型生成对应类别 EntryTag（customer、product、supplier、department 等）

#### Scenario: 摘要辅助识别Tag

- **WHEN** 导入科目为一级科目，但摘要中包含辅助核算关键词（如"行政部"、"项目A"、"北京"）
- **THEN** 系统从摘要中提取部门、项目、区域等维度信息
- **AND** 生成对应类别 EntryTag，标记 `tag_source="llm_suggested"`，`confidence=0.6`

#### Scenario: LLM辅助识别标记（Phase 2）

- **WHEN** 科目被扁平化但未能通过规则识别辅助核算维度（`requires_llm_resolution=true`）
- **AND** 分录属于往来类/成本费用类科目
- **THEN** 系统标记该分录需LLM进一步处理
- **AND** 记录 `requires_llm_resolution=true` 便于后续复盘和分批处理

### Requirement: 往来单位自动识别与关联

系统 SHALL 从科目下级段或对方单位字段中识别往来单位，并自动创建或关联 Counterparty 记录。

#### Scenario: 从科目段识别往来单位

- **WHEN** 导入科目为"1122应收账款-A客户"或"2202应付账款-供应商B"
- **THEN** 自动提取"客户A"或"供应商B"作为往来单位名称
- **AND** 创建或关联 Counterparty 记录
- **AND** 设置 `counterparty_id`

#### Scenario: 从对方单位字段识别

- **WHEN** 导入数据包含"对方单位"字段（如"客户A"）
- **THEN** 使用对方单位字段值创建或关联 Counterparty
- **AND** 设置 `counterparty_id`

### Requirement: EntryTag向量同步

系统 SHALL 在分录和Tag创建完成后，将标记为 `vector_pending=true` 的 EntryTag 同步到向量数据库。

#### Scenario: 向量同步成功

- **WHEN** 向量数据库可用
- **THEN** 同步成功后将 `vector_pending` 更新为 `false`

#### Scenario: 向量同步失败不阻塞主流程

- **WHEN** 向量数据库不可用
- **THEN** 记录同步失败日志
- **AND** 保留 `vector_pending=true`，不影响导入流程

### Requirement: TagCategory自动创建

系统 SHALL 在导入过程中自动创建所需的 TagCategory（如 customer、supplier、product、department 等），标记为系统分类（`is_system=true`）。

## MODIFIED Requirements

### Requirement: 导入任务创建接口

`POST /api/import-jobs` SHALL 支持可选参数 `source_type`，默认值为 `voucher_import`。

### Requirement: 导入任务处理逻辑

`process_import_job` SHALL 根据 `job.source_type` 选择处理分支：
- `voucher_import`：现有逻辑，直接解析为分录
- `audit_day_book`：调用序时簿专用处理逻辑，执行分组、平衡校验、完整性检测、科目解析、Tag生成、Counterparty关联

### Requirement: AccountingEntry模型扩展

`AccountingEntry` SHALL 新增字段：
- `resolved_account_code`：解析后的归一化科目编码
- `resolved_account_name`：解析后的归一化科目名称
- `counterparty_id`：关联的往来单位ID

## REMOVED Requirements

无。

## 设计决策记录

### 决策1：LLM辅助识别Tag（Phase 2）

**背景**：原始序时簿中可能缺少核算项目或二级科目信息，导致无法通过规则识别辅助核算维度。

**决策**：当前仅在 `account_tag_resolution_service.py` 中设置 `requires_llm_resolution` 标记位，不立即调用LLM。后续可根据标记批量调用LLM从摘要中识别维度并生成Tag。

**记录目的**：便于后期复盘和分阶段实施。

**触发条件**：
1. 科目被扁平化（原编码存在下级段）
2. 未能通过规则识别出任何辅助核算维度
3. 分录属于往来类/成本费用类科目（应收、应付、预收、预付、主营业务收入、生产成本、制造费用、管理费用、销售费用、财务费用）
4. 摘要不为空

### 决策2：强制二级科目编码硬编码

**背景**：不同财务软件的科目编码方案可能不同，但税法/会计准则强制要求的二级科目（如应交增值税明细）需要统一保留层级。

**决策**：当前使用 `MANDATORY_HIERARCHICAL_ACCOUNTS` 硬编码常见编码，并通过 `MANDATORY_HIERARCHICAL_KEYWORDS` 关键词兜底。后续可考虑从配置文件或数据库加载，支持自定义编码方案。

**记录目的**：明确当前约束，便于后续支持可配置化。
