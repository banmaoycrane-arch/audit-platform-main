# AI 凭证证据充分性、EntryTag 语义体系与重分类规则总 Spec

```text
Domain: D04/D05 交界 — 凭证草稿与证据链
Status: active-increment
Owner Spec: govern-ai-voucher-evidence-tags（本文档）
Depends On: document-parsing-engine, parser-dual-scenario-strategy.md
In Scope:
- 证据充分性判断 → draft 而非强行 post
- EntryTag 语义层、重分类规则
- 合同等多来源 → 同一 business_key 多草稿（增量 Task G1）
Out of Scope:
- 解析引擎分层、印章检测（→ document-parsing-engine / seal）
- 正式凭证 post、结账
Acceptance Level: 多草稿 UI + 审计留痕；与 parser-voucher 预览链路联调
```

> 多草稿模型见 [parser-dual-scenario-strategy.md](../../documents/parser-dual-scenario-strategy.md) §5.3。

## Why

AI 自动生成会计凭证不能只追求“自动化”，还必须符合会计证据链和审计可追溯要求。当原始资料不足以判断完整会计分录时，系统应当提示补充资料、暂存为 draft 草稿，而不是强行指定科目。

同时，EntryTag 不只是普通标签，而是承接二级科目、辅助核算、摘要、对方单位、业务语义和向量风险识别的统一机制。主科目与对方单位也不应被简单理解为借方或贷方固定属性，而应服务于复式记账、余额正负方向和重分类判断。

## What Changes

- 建立 AI 生成凭证前的原始资料充分性判断规则。
- 当证据不足时，AI 不强行生成正式凭证，而是生成 draft 草稿并提示需要补充的资料类型。
- 支持用户从 AI draft 切换到人工录入路径补足会计分录信息。
- 对 AI 转人工的情况写入系统日志，满足审计追溯。
- 将 EntryTag 定义为统一语义层，覆盖：
  - 二级/明细科目语义
  - 辅助核算项目
  - 摘要关键词
  - 对方单位语义
  - 原始资料与分录之间的业务联系
- 明确主科目保留国家会计准则定义的一级科目或系统主科目，其他细分维度优先进入 EntryTag。
- 明确余额方向由正负数和重分类规则决定，不简单依赖科目初始资产/负债归属。
- 本 spec 是总规则 spec，后续实施按三个阶段推进。

## Impact

- Affected specs:
  - `auto-generate-entries-from-source`：扩展 AI 生成前的证据充分性判断。
  - `unify-voucher-input-modes`：AI 路径与人工路径之间增加可追溯切换。
  - `entry-tag-vector-sync`：EntryTag 从辅助核算标签升级为统一语义识别层。
  - `entity-semantic-mapping`：对方单位与主体语义识别继续复用。
  - `summary-library`：摘要成为 EntryTag 的重要来源。
- Affected code:
  - `backend/app/services/entry_generation_service.py`
  - `backend/app/services/entry_tag_service.py`
  - `backend/app/services/entry_tag_vector_service.py`
  - `backend/app/api/routes_entry_generation.py`
  - `backend/app/models` 或 `backend/app/db/models.py`
  - `frontend/src/pages/AccountingMode/Step2ImportSource.tsx`
  - `frontend/src/pages/AccountingMode/Step3GenerateEntries.tsx`
  - `frontend/src/api/client.ts`

## ADDED Requirements

### Requirement: AI 原始资料充分性判断

The system SHALL evaluate whether uploaded source documents provide enough evidence to generate a complete accounting voucher.

#### Scenario: 发票已上传但未能确认收款

- **WHEN** 用户上传销售发票但未上传银行流水或收款回单
- **THEN** 系统 SHALL not directly determine the counter account as 银行存款
- **AND** 系统 SHALL提示用户补充银行流水或收款回单
- **AND** 如果无法证明已收款，系统 SHALL 暂存为 draft 草稿

#### Scenario: 发票和银行流水均充分

- **WHEN** 用户上传销售发票且银行流水可匹配到收款
- **THEN** 系统 MAY generate a draft voucher using 银行存款 as the counter account
- **AND** 系统 SHALL保留发票与银行流水的证据引用

#### Scenario: 流水不足以证明交易性质

- **WHEN** 用户上传银行流水但无法判断交易合同、业务性质或对方单位
- **THEN** 系统 SHALL提示补充合同、订单、结算单或其他业务资料
- **AND** 系统 SHALL暂存为 draft 草稿

### Requirement: 不强行生成正式凭证

The system SHALL keep insufficient AI-generated results in draft status instead of forcing accounting recognition.

#### Scenario: 证据不足进入 draft

- **WHEN** AI 判断资料不足以完整生成会计凭证
- **THEN** 系统 SHALL生成 draft 草稿
- **AND** 草稿 SHALL包含缺失资料类型、缺失原因、当前可识别信息和建议下一步
- **AND** 草稿 SHALL not be committed to standard AccountingEntry until user review or supplementation

### Requirement: AI 转人工录入审计日志

The system SHALL log when a user switches from AI-generated draft to manual voucher entry.

#### Scenario: 用户改为人工补录

- **WHEN** AI draft 资料不足，用户选择切换到人工录入补充分录
- **THEN** 系统 SHALL记录系统日志
- **AND** 日志 SHALL包含原 draft id、用户、时间、切换原因、已识别资料、人工补充字段

### Requirement: EntryTag 统一语义层

The system SHALL treat EntryTag as the unified semantic layer for voucher details beyond main accounting subjects.

#### Scenario: 二级科目语义进入 EntryTag

- **WHEN** 凭证涉及“应交税费-应交增值税-销项税额”等细分语义
- **THEN** 系统 SHALL保留主科目为会计准则定义科目
- **AND** 将“应交增值税”“销项税额”等细分语义写入 EntryTag

#### Scenario: 摘要语义进入 EntryTag

- **WHEN** 凭证摘要包含客户、项目、业务类型、合同、发票号、结算方式等语义
- **THEN** 系统 SHALL从摘要中提取 EntryTag
- **AND** 这些 EntryTag SHALL用于后续向量风险识别

#### Scenario: 原始资料与分录建立语义联系

- **WHEN** 凭证由发票、合同、银行流水等原始资料生成
- **THEN** 系统 SHALL用 EntryTag 建立分录与原始资料之间的业务联系
- **AND** 向量库 SHALL可基于这些标签识别业务、凭证和资料之间的风险关系

### Requirement: 主科目与对方单位不绑定借贷方向

The system SHALL not treat main account and counterparty as fixed debit-side or credit-side concepts.

#### Scenario: 往来科目余额重分类

- **WHEN** 往来余额因正负方向变化需要重分类
- **THEN** 系统 SHALL根据余额方向和重分类规则判断列报性质
- **AND** 不 SHALL仅根据初始科目属于资产或负债来决定最终定性

#### Scenario: 对方单位只是交易对象语义

- **WHEN** 分录存在对方单位
- **THEN** 对方单位 SHALL表示交易对象或业务对象
- **AND** 不 SHALL因为分录借贷方向不同而改变对方单位本身语义

## MODIFIED Requirements

### Requirement: AI 自动生成凭证流程

AI 自动生成流程 SHALL 从“解析资料后直接生成凭证草稿”修改为“先做证据充分性判断，再决定生成可复核凭证草稿、提示补资料或进入 draft 暂存”。

### Requirement: EntryTag 业务定位

EntryTag SHALL 从“辅助核算标签”升级为“凭证语义识别与风险量化基础层”，用于统一承接除主科目以外的细分科目、辅助核算、摘要、业务资料联系等信息。

### Requirement: 往来和重分类判断

往来类判断 SHALL 从“科目类别决定资产/负债定性”修改为“主科目记录初始会计分类，最终列报性质由余额方向、正负数和重分类规则决定”。

## REMOVED Requirements

无。
