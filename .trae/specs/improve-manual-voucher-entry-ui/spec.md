# 手工凭证录入界面优化与提交稳定性 Spec

## Why

当前手工凭证录入界面较简陋，凭证日期、凭证字号、会计期间、科目、对方单位等字段没有充分体现真实财务软件的录入习惯和账簿上下文，且用户反馈“提交人工凭证失败：Internal Server Error”，需要优先修复提交稳定性。

从会计实务看，手工凭证录入不是简单填几列分录，而应基于账簿、会计主体、会计期间、已结账状态、科目档案和往来性质自动提供默认值、选择控件和必要校验。

## What Changes

- 修复人工凭证提交 Internal Server Error，确保错误返回有业务语义。
- 优化手工凭证录入 UI，分为凭证基本信息、会计期间、分录明细、附件/归档提示等区域。
- 将“凭证字”和“凭证号”拆为两个独立字段，不再混为一个 `记-001` 字符串输入。
- 凭证日期使用日期控件，并根据会计期间和账簿状态自动默认。
- 会计期间使用选择控件，优先选择当前打开期间；如上一期间已结账，默认建议下一自然月期间。
- 科目代码支持从会计科目档案选择，也支持跳转到会计科目模块新增科目。
- 自定义新增科目时，带上当前凭证日期/期间作为参考上下文；正式生效日期仍由用户在科目模块人工确认。
- 对方单位不作为所有分录的必填项，仅当科目属于往来性质时提示或要求填写。
- 提交时保留项目归档所需的上下文信息，便于后续继续推进项目和审计追溯。

## Impact

- Affected specs:
  - `unify-voucher-input-modes`：增强传统人工录入路径。
  - `auto-generate-entries-from-source`：复用会计期间、科目、对方单位档案。
  - `basic-data-pages`：新增科目时需要跳转到会计科目模块。
  - `accounting-period-snapshot`：期间选择需要尊重 open/closed 状态。
  - `govern-ai-voucher-evidence-tags`：保留 EntryTag 和项目归档上下文。
- Affected code:
  - `frontend/src/pages/AccountingMode/Step2ImportSource.tsx`
  - `frontend/src/api/client.ts`
  - `frontend/src/pages/BasicData/ChartOfAccountsPage.tsx`
  - `backend/app/api/routes_entry_generation.py`
  - `backend/app/services/entry_generation_service.py`
  - `backend/app/api/routes_coa.py`
  - `backend/app/api/routes_accounting_periods.py`
  - 相关后端测试与前端检查

## ADDED Requirements

### Requirement: 人工凭证提交稳定性

The system SHALL allow manual voucher submission without Internal Server Error for valid balanced manual vouchers.

#### Scenario: 有效人工凭证提交成功

- **WHEN** 用户录入凭证基本信息、会计期间和借贷平衡的分录明细
- **THEN** 系统 SHALL 成功提交人工凭证
- **AND** 返回落库分录数量、分录 ID 和 job ID

#### Scenario: 提交失败返回业务语义

- **WHEN** 人工凭证提交失败
- **THEN** 系统 SHALL 返回明确业务错误信息
- **AND** 不 SHALL 只显示 Internal Server Error

### Requirement: 凭证字与凭证号拆分

The system SHALL separate voucher type and voucher number in the manual voucher entry form.

#### Scenario: 用户选择凭证字

- **WHEN** 用户录入人工凭证
- **THEN** 凭证字 SHALL 使用下拉控件选择，例如 记、银、收、付、转、工
- **AND** 凭证号 SHALL 使用独立数字或文本控件录入/自动建议

#### Scenario: 提交时兼容现有凭证号字段

- **WHEN** 系统提交人工凭证
- **THEN** 系统 MAY 拼装现有 `voucher_no` 字段用于兼容旧结构
- **AND** 前端 SHALL 保留 voucher_type 与 voucher_number 的独立录入语义

### Requirement: 凭证日期和会计期间默认

The system SHALL default voucher date and accounting period based on ledger and accounting period context.

#### Scenario: 存在打开期间

- **WHEN** 当前账簿/会计主体存在 open 或 reopened 会计期间
- **THEN** 系统 SHALL 默认选择该期间
- **AND** 凭证日期 SHALL 默认在该期间范围内

#### Scenario: 上一期间已结账

- **WHEN** 上一会计期间已 closed
- **THEN** 系统 SHALL 建议下一自然月期间
- **AND** 凭证日期 SHALL 默认指向下一自然月的合理日期

### Requirement: 科目选择与新增科目导航

The system SHALL allow users to select account code/name from Chart of Accounts and navigate to account management for new accounts.

#### Scenario: 选择已有科目

- **WHEN** 用户在分录行输入科目代码或名称
- **THEN** 系统 SHALL 提供会计科目选择控件
- **AND** 选择后自动填充科目代码和科目名称

#### Scenario: 新增自定义科目

- **WHEN** 用户发现所需科目不存在
- **THEN** 系统 SHALL 提供跳转到会计科目模块的入口
- **AND** SHALL 带上当前凭证日期、期间和已输入关键词作为上下文
- **AND** 科目正式生效日期 SHALL 在科目模块由用户人工确认

### Requirement: 对方单位按往来性质控制

The system SHALL not require counterparty for every manual voucher line.

#### Scenario: 非往来科目不强制对方单位

- **WHEN** 分录科目不是往来性质科目
- **THEN** 对方单位 SHALL 可为空

#### Scenario: 往来科目提示对方单位

- **WHEN** 分录科目属于应收、预收、应付、预付、其他应收、其他应付等往来性质
- **THEN** 系统 SHALL 提示或要求填写对方单位
- **AND** 该提示 SHALL 基于科目代码/名称判断

### Requirement: 项目归档上下文

The system SHALL preserve enough context for project archive and future continuation.

#### Scenario: 人工凭证提交保留上下文

- **WHEN** 人工凭证提交
- **THEN** 系统 SHALL 在 metadata 或日志中保留输入模式、期间、凭证日期、凭证字、凭证号、来源路径、科目上下文和必要归档提示
- **AND** 这些信息 SHALL 支持后续项目复盘和审计追溯

## MODIFIED Requirements

### Requirement: 手工凭证录入页面

手工凭证录入页面 SHALL 从简易表格升级为基于控件的凭证录入界面，包括凭证基本信息、期间选择、分录明细、科目选择、对方单位规则和归档上下文提示。

### Requirement: 人工凭证校验

人工凭证校验 SHALL 保留借贷平衡校验，并新增凭证日期、期间、凭证字、凭证号、科目选择、往来科目对方单位提示等校验。

## REMOVED Requirements

无。
