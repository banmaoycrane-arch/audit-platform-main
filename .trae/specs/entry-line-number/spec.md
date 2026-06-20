# 分录行号管理 Spec

## Why

当前 `AccountingEntry` 只用全局 `id`，没有“同一凭证字号下的分录行号”。在财务凭证的口径下，**同一张凭证内的分录必须有可读、稳定、连续的行号**（例如“记-001 / 行 1”“记-001 / 行 2”），便于：

- 与原始凭证扫描件、纸质凭证逐行核对
- 审计追溯和审计语言表述（“记-001 第 3 行 借：管理费用”）
- 同一凭证内的借贷平衡逐行检查
- 后期合并、拆分、调整凭证时保持稳定引用
- 导出标准账套时输出标准的明细行号

非同一凭证字号的分录之间不需要统一编号，避免引入跨凭证的隐式顺序假设。

## What Changes

- 在“自适应导入引擎”模块中补充“同一凭证下的分录行号”需求细节。
- `AccountingEntry` 新增字段 `entry_line_no`：在同一组织 + 同一凭证字 + 同一凭证号下唯一且从 1 开始递增。
- 导入与解析阶段：每解析出一条分录，按所在凭证（凭证字 + 凭证号）顺序分配 `entry_line_no`。
- 审计/校验/展示侧使用 `entry_line_no` 替代或补充“行序号”。
- 不要求跨凭证全局唯一，**仅在同一凭证字号下唯一**。

> 本次需求归入并补充模块：`.trae/specs/adaptive-import-engine/`（自适应导入引擎）。  
> 本 spec 仅作为该模块的需求增量记录，不再单独搭建模块。

## Impact

- 影响的能力 / Specs：
  - `adaptive-import-engine`：导入时分配分录行号
  - `summary-library`：审计语言表述支持“某凭证第 N 行”
  - `business-cycle-audit`：审计发现可定位到行
  - `accounting-period-snapshot`：快照需要保留分录行号
- 影响的代码（以现状为准）：
  - `backend/app/db/models.py` 中 `AccountingEntry`
  - `backend/app/services/import_service.py`
  - `backend/app/services/file_parser_service.py`
  - `backend/app/services/adaptive_mapper.py`
  - `backend/app/services/audit_test_service.py`
  - `backend/app/api/routes_entries.py` 返回字段
  - 前端分录展示与审计发现展示

## ADDED Requirements

### Requirement: 分录行号字段

系统 SHALL 为每条会计分录提供 `entry_line_no` 字段，表示该分录在所属凭证内的行号。

#### Scenario: 同一凭证下行号从 1 开始递增

- **WHEN** 一张凭证 `记-2026-001` 包含 3 条分录
- **THEN** 这 3 条分录的 `entry_line_no` 分别为 `1`、`2`、`3`

#### Scenario: 不同凭证之间行号互不影响

- **WHEN** 凭证 `记-2026-001` 有 3 条分录、凭证 `记-2026-002` 有 2 条分录
- **THEN** `记-2026-002` 的分录 `entry_line_no` 仍从 `1` 开始

#### Scenario: 缺少凭证字号时降级

- **WHEN** 某条分录解析时 `voucher_no` 缺失
- **THEN** `entry_line_no` 默认为 `1`，但 `voucher_no` 视为该分录独立分组

### Requirement: 导入流程分配行号

自适应导入引擎 SHALL 在导入或解析分录时，按解析顺序为同一 `(organization_id, voucher_word, voucher_no)` 分组分配连续的 `entry_line_no`。

#### Scenario: 导入 Excel 同一凭证多行

- **WHEN** Excel 中 `记-2026-001` 含 3 行分录，按行顺序解析
- **THEN** 三行分录的 `entry_line_no` 按解析顺序依次为 `1, 2, 3`

#### Scenario: 二次重新解析覆盖

- **WHEN** 同一导入任务再次解析同一张凭证
- **THEN** 行号 SHALL 与首次解析保持稳定的相对顺序

### Requirement: API 与前端展示

API SHALL 在分录返回结构中包含 `entry_line_no`。前端审计与凭证展示 SHALL 显示该行号。

#### Scenario: 分录列表 API

- **WHEN** 调用 `GET /api/entries`
- **THEN** 返回的每条分录 JSON 包含 `entry_line_no`

#### Scenario: 审计发现描述使用行号

- **WHEN** 审计测试针对凭证 `记-2026-001` 第 2 行的金额异常生成发现
- **THEN** 审计语言可表述为“记-2026-001 第 2 行 借方金额与发票不一致”

## MODIFIED Requirements

### Requirement: AccountingEntry 模型

`AccountingEntry` 在原字段基础上增加 `entry_line_no: int`，并增加非唯一索引 `(organization_id, voucher_word, voucher_no, entry_line_no)`，便于同一凭证内排序与定位。

### Requirement: 自适应导入引擎输出

`adaptive-import-engine` 在生成 `AccountingEntry` 时 SHALL 同步写入 `entry_line_no`，未提供 `voucher_no` 的分录视为独立分组，行号默认为 `1`。

## REMOVED Requirements

无。
