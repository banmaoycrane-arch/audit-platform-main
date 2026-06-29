# 审计工作底稿电子表格化实施计划

## Summary

用户提出：审计系统中的工作底稿库，底稿一般应对应各类测试文件。例如固定资产底稿应有一个底稿首页，并按固定路径让现场人员编制折旧测试等正式表格，后面可以附临时 sheet。因此，大部分审计底稿本质上是电子表格文件。

本计划判断：

- 不建议一开始直接引入完整在线 Excel 编辑器。
- 建议先把工作底稿从“索引 + 版本记录”升级为“以 `.xlsx` 为正式载体的文件型底稿”。
- 后端优先复用当前已有 `openpyxl` 生成标准底稿 Excel。
- 前端先支持下载、预览、版本、复核，不先做复杂单元格在线编辑。
- 等固定资产模块补齐基础数据后，再做固定资产折旧测试底稿模板。

核心方向：

```text
支持性文件 / 审计程序数据
  → 生成标准审计底稿 Excel
  → WorkpaperVersion 记录文件快照
  → 下载 / 预览 / 修订 / 提交复核
  → PR / Review / Merge 归档
```

## Current State Analysis

### 1. 当前工作底稿实现

前端工作底稿页面：

- [WorkpapersPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/WorkpapersPage.tsx)

当前能力：

- 展示底稿索引；
- 展示版本数、当前版本、状态、归档路径；
- 同步归档底稿；
- 导出底稿目录 JSON；
- 查看底稿版本历史。

当前缺口：

- 不能打开 Excel；
- 不能下载底稿文件；
- 不能预览底稿 sheet；
- 不能新建电子表格底稿；
- 不能把审计程序结果生成正式底稿 Excel。

后端工作底稿 API：

- [routes_workpapers.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_workpapers.py)

当前接口：

- `GET /api/workpapers/index`
- `POST /api/workpapers/index`
- `GET /api/workpapers/index/{index_id}`
- `POST /api/workpapers/register`
- `POST /api/workpapers/sync-from-archive`
- `POST /api/workpapers/index/{index_id}/revise`
- `PATCH /api/workpapers/versions/{version_id}`
- `GET /api/workpapers/export`

当前导出是目录 JSON，不是 Excel 底稿文件。

底稿服务：

- [workpaper_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/workpaper_service.py)

当前能力：

- SourceFile 可挂接为 WorkpaperVersion；
- 支持版本 `1.0`、`1.1`；
- 支持旧版本 `superseded`；
- 支持底稿索引按审计领域归类；
- 状态包括 `draft`、`submitted`、`reviewed`、`superseded`。

当前本质：

> 目录索引 + 来源文件版本记录，不是完整电子表格底稿系统。

### 2. 当前模型能力

模型位于：

- [models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py#L1715-L1753)

当前 `WorkpaperIndex` 字段：

- `ledger_id`
- `project_id`
- `parent_id`
- `index_no`
- `title`
- `audit_area`
- `archive_path`
- `source_module_key`
- `sort_order`

当前 `WorkpaperVersion` 字段：

- `workpaper_index_id`
- `source_file_id`
- `version_no`
- `status`
- `prepared_by`
- `reviewed_by`
- `change_reason`
- `supersedes_id`

缺少电子表格底稿常用字段：

- `storage_path`
- `file_name`
- `file_hash`
- `file_size`
- `mime_type`
- `template_code`
- `sheet_count`
- `workbook_metadata`
- `generated_from`

### 3. 当前 Excel 能力

后端依赖：

- [backend/pyproject.toml](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/pyproject.toml)

已有：

- `pandas`
- `openpyxl`

未发现：

- `xlsxwriter`
- `xlrd`

现有 Excel 读写：

- [file_parser_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/file_parser_service.py)：会计凭证 Excel / CSV 导入。
- [routes_parser_engine.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_parser_engine.py)：Excel sheet 列表识别。
- [routes_export.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_export.py)：凭证清单 Excel 导出。
- [audit_report_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_report_service.py)：审计报告 Excel 导出。

结论：

- 当前已有 `openpyxl`，足以先生成 `.xlsx` 底稿模板。
- 当前前端没有 SheetJS、ExcelJS、Handsontable、Luckysheet、Univer 等电子表格编辑器。
- 不建议第一步引入大型在线表格依赖。

### 4. 当前审计程序数据来源

已有较接近底稿的结构化功能：

1. 银行调节表
   - [bank_reconciliation_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/bank_reconciliation_service.py)
   - [BankReconciliationPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Bank/BankReconciliationPage.tsx)

2. 往来函证控制表
   - [confirmation_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/confirmation_service.py)
   - [ConfirmationsPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/ConfirmationsPage.tsx)

3. 采购三单匹配
   - [three_way_match_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/three_way_match_service.py)
   - [PurchaseMatchPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/PurchaseMatchPage.tsx)

这些功能目前是数据库记录 + 页面表格，不是正式 Excel 底稿。

### 5. 固定资产/折旧现状

前端：

- [FixedAssetsWorkspace.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Workspaces/FixedAssetsWorkspace.tsx)
- `/fixed-assets/cards`、`/fixed-assets/depreciation` 当前为占位。

当前未发现：

- 固定资产卡片模型；
- 折旧政策模型；
- 折旧计提服务；
- 固定资产折旧测试服务；
- 固定资产折旧测试底稿 Excel 模板。

因此，固定资产折旧测试底稿应放在第二阶段或第三阶段，不能作为第一批实现对象。

## Decision: 直接引用电子表格依赖还是针对性调整？

### 不建议直接上完整在线电子表格依赖

不建议第一步引入：

- Luckysheet；
- Univer；
- Handsontable；
- JSpreadsheet；
- 完整 SheetJS 在线编辑方案。

原因：

1. 审计底稿的核心不是“像 Excel 一样随意编辑”，而是“可追溯、可复核、可归档”。
2. 完整在线 Excel 会带来复杂问题：公式、格式、批注、合并单元格、权限、版本冲突、未保存状态。
3. 账簿/项目切换后，如果在线编辑缓存处理不好，会产生审计证据错配风险。
4. 当前项目已有 `openpyxl`，可以低成本生成标准 `.xlsx` 文件。

### 推荐针对性调整

推荐做“文件型电子表格底稿”：

1. 后端用 `openpyxl` 生成标准 Excel 底稿。
2. 每个 `WorkpaperVersion` 记录一个底稿文件快照。
3. 前端支持下载、预览 sheet、提交复核。
4. 指定区域如“审计结论、复核意见”后续可做受控编辑。
5. 不把整个 Excel 单元格编辑器作为第一阶段目标。

## Proposed Changes

### Change 1：扩展 WorkpaperVersion 文件快照字段

文件：

- [models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py#L1737-L1753)
- 新增 Alembic 迁移文件

建议新增字段：

```text
file_name
file_ext
mime_type
storage_path
file_hash
file_size
template_code
sheet_count
workbook_metadata
generated_from
```

业务含义：

- `storage_path`：底稿 Excel 文件实际存储路径。
- `file_hash`：文件内容哈希，用于审计追溯。
- `template_code`：使用哪个底稿模板生成。
- `workbook_metadata`：sheet 名称、行列数、生成来源等。
- `generated_from`：例如 `bank_reconciliation`、`confirmation`、`purchase_match`、`manual_upload`。

为什么：

- 当前版本只知道来源 `SourceFile`，不知道底稿 Excel 文件自身。
- 审计底稿需要能够下载、复核、归档、追溯版本。

### Change 2：新增底稿 Excel 模板生成服务

新增文件：

- `backend/app/services/workpaper_excel_service.py`

功能：

1. 用 `openpyxl` 生成 `.xlsx`。
2. 提供统一方法：

```python
generate_workpaper_excel(template_code, context, output_path) -> WorkpaperFileSnapshot
```

3. 第一批模板：

| template_code | 底稿名称 | sheet 设计 |
|---|---|---|
| `workpaper_index_catalog` | 底稿目录 | 底稿索引、版本、状态、归档路径 |
| `bank_reconciliation` | 银行存款余额调节表 | 首页、调节项目、未达账项、审计结论 |
| `confirmation_control` | 往来函证控制表 | 首页、函证清单、回函差异、替代测试、审计结论 |
| `purchase_three_way_match` | 采购与付款三单匹配底稿 | 首页、合同清单、发票匹配、入库匹配、差异清单、审计结论 |

固定资产折旧测试底稿暂不列入第一批，等待固定资产模块基础数据完成。

### Change 3：新增底稿文件下载 API

文件：

- [routes_workpapers.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_workpapers.py)

新增接口：

```text
GET /api/workpapers/versions/{version_id}/download
```

功能：

- 校验当前账簿权限；
- 根据 `WorkpaperVersion.storage_path` 返回 `.xlsx` 文件；
- 如果版本没有文件快照，返回明确提示。

为什么：

- 工作底稿作为 Excel 文件，最基本能力是下载和归档。

### Change 4：新增底稿 Excel 生成 API

文件：

- [routes_workpapers.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_workpapers.py)
- [workpaper_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/workpaper_service.py)
- 新增 `workpaper_excel_service.py`

新增接口：

```text
POST /api/workpapers/index/{index_id}/generate-excel
```

请求参数：

```json
{
  "template_code": "bank_reconciliation",
  "source_context": {
    "procedure_run_id": 1,
    "source_file_id": 2
  }
}
```

功能：

- 根据模板生成 Excel；
- 写入 `WorkpaperVersion` 新版本；
- 旧版本状态改为 `superseded`；
- 返回新的底稿版本信息。

### Change 5：底稿目录导出支持 Excel

文件：

- [routes_workpapers.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_workpapers.py)
- [workpaper_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/workpaper_service.py)
- 新增 `workpaper_excel_service.py`

现状：

- `GET /api/workpapers/export` 返回 JSON。

计划：

- 增加 `format=xlsx|json`。
- 默认仍可保留 JSON。
- `format=xlsx` 时生成“底稿目录.xlsx”。

为什么：

- 审计实务中底稿目录更常用 Excel 或可归档文件。

### Change 6：前端 WorkpapersPage 增加下载/生成/预览入口

文件：

- [WorkpapersPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/WorkpapersPage.tsx)
- [client.ts](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/api/client.ts)

新增能力：

1. 版本列表增加：
   - 下载底稿；
   - 生成 Excel；
   - 查看 sheet 概览。

2. 顶部按钮增加：
   - 导出目录 Excel；
   - 导出目录 JSON。

3. 底稿说明改为：

```text
审计工作底稿以电子表格文件为主要载体。系统可根据审计程序生成标准底稿 Excel，底稿版本进入复核、修订和归档流程；支持性文件作为原始证据来源保留。
```

### Change 7：新增只读 Sheet 预览接口

文件：

- [routes_workpapers.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_workpapers.py)
- 新增或复用 `workpaper_excel_service.py`

新增接口：

```text
GET /api/workpapers/versions/{version_id}/preview
```

返回：

```json
{
  "sheets": [
    {
      "name": "首页",
      "rows": 20,
      "columns": 8,
      "preview": [["索引号", "底稿名称"], ...]
    }
  ]
}
```

第一阶段只读预览，不做编辑。

为什么：

- 用户能快速判断底稿内容是否正确。
- 不引入大型在线 Excel 编辑器。

### Change 8：固定资产折旧测试底稿后置

固定资产底稿是用户提到的典型例子，但当前固定资产模块尚未建模。

后续单独规划：

1. 固定资产卡片；
2. 折旧政策；
3. 本期折旧计算；
4. 折旧凭证勾稽；
5. 折旧测试底稿 Excel 模板；
6. 临时 sheet 附件机制。

本次计划不直接实现固定资产折旧测试底稿。

## Assumptions & Decisions

1. 工作底稿以 `.xlsx` 为第一正式文件载体。
2. 后端优先使用已有 `openpyxl`。
3. 前端第一阶段不引入完整在线 Excel 编辑器。
4. 第一批底稿模板选择已有数据基础的审计程序：
   - 银行调节；
   - 往来函证；
   - 采购三单匹配；
   - 底稿目录。
5. 固定资产折旧测试底稿后置，等待固定资产模块数据模型完成。
6. 临时 sheet 第一阶段可作为模板中的“临时附表”保留空 sheet，而不是复杂在线新增 sheet。
7. 底稿版本保存的是文件快照，不直接覆盖旧版本。

## Verification Steps

### 后端验证

1. 创建或同步一个底稿索引。
2. 调用生成 Excel 接口。
3. 检查生成新的 `WorkpaperVersion`。
4. 检查旧版本是否 `superseded`。
5. 检查 `storage_path`、`file_hash`、`sheet_count` 等字段。
6. 下载 `.xlsx` 文件，确认可以用 Excel/WPS 打开。
7. 调用预览接口，确认能返回 sheet 列表和前几行内容。

### 前端验证

1. 打开 http://127.0.0.1:5173/audit/workpapers
2. 点击“同步归档底稿”。
3. 选择一个底稿索引。
4. 点击“生成 Excel”。
5. 在版本列表中点击“下载”。
6. 下载的文件应为 `.xlsx`。
7. 点击“预览”，应能看到 sheet 名称和预览数据。
8. 导出底稿目录 Excel，确认文件可打开。

### 审计实务验证

1. 银行调节底稿应包含：
   - 首页；
   - 调节项目；
   - 未达账项；
   - 审计结论。

2. 往来函证底稿应包含：
   - 首页；
   - 函证清单；
   - 回函差异；
   - 替代测试；
   - 审计结论。

3. 采购三单匹配底稿应包含：
   - 首页；
   - 合同清单；
   - 发票匹配；
   - 入库匹配；
   - 差异清单；
   - 审计结论。

## Out of Scope

本计划明确不做：

1. 不实现完整在线 Excel 编辑器。
2. 不引入 Luckysheet、Univer、Handsontable 等大型依赖。
3. 不实现固定资产卡片和折旧计算主模块。
4. 不直接做固定资产折旧测试底稿。
5. 不修改正式凭证、报表、结账规则。
6. 不把支持性文件直接当成工作底稿。
7. 不允许覆盖旧底稿版本，只能生成新版本。

## Recommended Execution Order

1. 数据模型扩展：WorkpaperVersion 文件快照字段。
2. 新增 Excel 生成服务。
3. 底稿目录 Excel 导出。
4. 底稿版本下载 API。
5. 底稿版本只读预览 API。
6. 前端 WorkpapersPage 增加生成、下载、预览按钮。
7. 第一批模板：底稿目录、银行调节、函证控制、三单匹配。
8. 构建、后端导入、接口基础测试。

## Final Recommendation

本项目当前最合适的路线是：

> **不直接依赖大型前端电子表格编辑器，而是针对审计底稿业务做“Excel 文件型底稿 + 模板生成 + 下载预览 + 版本复核”的定制调整。**

这样既符合审计实务，也能控制实现复杂度和财务数据风险。
