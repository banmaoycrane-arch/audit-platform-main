# 账簿、支持性文件与审计工作底稿边界统一计划

## Summary

本计划用于统一系统中“账簿/账簿、支持性文件、审计工作底稿、项目”的边界和用户可理解口径。

用户业务判断：

- “账簿”强调一个具体会计主体的核算范围和数据边界。
- 现有“账簿文件”正式名称应调整为“支持性文件”。
- 支持性文件是每个账簿/账簿对应的原始支撑资料，例如客户合同、供应商合同、发票、银行回单、其他原始文件。
- 支持性文件必须关联到对应账簿/账簿。
- 审计师安装/创建项目管理后，再把支持性文件归类到项目中，形成“账簿 + 项目”双绑定。
- 审计工作底稿不是原件，而是对支持性文件、审计程序、审计结论、PR/Issue/复核授权流程加工后的成果文件，便于归档和复核认可。
- 支持性文件原则上是不可篡改原件；允许修改的应是分类、关联、备注、标签等元数据，不应修改原文件本体。

本计划不立即修改代码。待确认后执行。

## Current State Analysis

### 1. 需求域归属

根据 [requirements-domain-index.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/requirements-domain-index.md)：

- 主归属域：D02 团队、账簿、项目、上下文。
- 相关域：D05 原始资料导入与解析，D06 审计证据与审计流程。
- Owner Spec 建议：
  - D02：`ledger-register-project-concept-unification`
  - D05：`adaptive-import-engine`
  - D06：`audit-github-style-workflow-plan.md`

本次计划不进入 D04 凭证生命周期，不修改正式凭证、报表、结账逻辑。

### 2. 现有核心概念文档

现有 [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/core-business-concepts-boundary.md) 已定义：

- `Ledger` = 会计账簿，正式核算数据边界。
- `Project` = 审计、记账、税务等工作任务边界。
- `SourceFile` = 原始资料文件，合同、发票、银行回单、PDF 等证据载体。
- `Register` = 业务模块台账，不等于会计账簿，不直接替代凭证。

当前需要补充和纠偏：

- 用户界面中的“账簿文件”容易被误解为“账簿本身的文件”，应改为“支持性文件”。
- “审计工作底稿”应明确为加工成果，与不可篡改原始支持性文件分层。
- “支持性文件”与“工作底稿”之间应有清晰链路：原件 → 解析/归类 → 台账/审计程序 → 底稿版本 → 复核/归档。

### 3. Ledger / 账簿 / 账簿现状

后端模型 [ledger.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/models/ledger.py) 中：

- `Ledger` 表示账簿，字段包括 `id`、`name`、`team_id`、`status`、`accounting_start_date` 等。
- 模型注释写着“账簿实体：对应财务实务中的账簿或核算主体”，这容易与前端“账簿管理”混淆。

前端存在 [LedgerBooksPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/LedgerBooksPage.tsx)，用于序时簿、总账、明细账查询。

计划口径：

- 技术实体仍保留 `Ledger`，避免大规模重命名。
- 用户说明中把 Ledger 解释为“核算账簿/账簿边界：某一会计主体核算范围的数据边界”。
- 前端已有“账簿管理”页面继续表示序时簿、总账、明细账，不与“支持性文件”混用。

### 4. Project 与 Ledger 双绑定现状

[project_ledger.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/models/project_ledger.py) 已有 `ProjectLedger` 多对多表：

- `project_id`
- `ledger_id`
- 唯一约束 `uq_project_ledger`

这已经支持一个项目绑定多个账簿/账簿，一个账簿/账簿也可被多个项目引用。

### 5. SourceFile / ImportJob 现状

[models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py#L18-L58) 中：

- `ImportJob` 已有 `ledger_id` 和 `project_id`。
- `SourceFile` 已有 `ledger_id`、`import_job_id`、`counterparty_id`、`filename`、`file_type`、`storage_path`、`text_extract_status`、`extracted_text`、`notes`。
- `SourceFile` 当前没有直接 `project_id` 字段。

现状含义：

- 支持性文件当前技术载体就是 `SourceFile`。
- 支持性文件直接绑定账簿/账簿：`SourceFile.ledger_id`。
- 项目归属通常通过 `ImportJob.project_id`、`ProjectLedger`、归档 metadata 推导。

### 6. 当前“账簿文件”页面

[LedgerFilesPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/LedgerFilesPage.tsx) 当前标题和菜单使用“账簿文件”。

页面功能包括：

- 按当前账簿加载文件；
- 展示文件类型、解析状态、往来单位、归档路径、项目、期间；
- 支持绑定/解绑账簿；
- 支持编辑文件名、文件类型、备注；
- 支持删除文件。

计划调整：

- 页面名称从“账簿文件”改为“支持性文件”。
- 文案明确“支持性文件是原始资料原件，不是审计工作底稿”。
- 编辑功能改为“编辑文件元数据”，避免让用户理解为可以修改原件。
- 删除功能需要提示“删除支持性文件会影响审计证据链”，后续可考虑改成归档/作废而非物理删除。

### 7. 审计工作底稿现状

前端 [WorkpapersPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/WorkpapersPage.tsx) 已有“工作底稿库”。

后端 [routes_workpapers.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_workpapers.py) 和 [workpaper_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/workpaper_service.py) 已支持：

- 底稿索引；
- 底稿版本；
- 从归档支持性文件同步底稿；
- 创建底稿索引；
- 注册 source file 为底稿版本；
- 修订底稿；
- 更新版本状态；
- 导出底稿目录。

[models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py#L1715-L1753) 中已有：

- `WorkpaperIndex.ledger_id`
- `WorkpaperIndex.project_id`
- `WorkpaperVersion.source_file_id`
- `WorkpaperVersion.status`
- `WorkpaperVersion.prepared_by`
- `WorkpaperVersion.reviewed_by`
- `WorkpaperVersion.change_reason`
- `WorkpaperVersion.supersedes_id`

这说明“支持性文件 → 工作底稿版本”的基本链路已存在。

### 8. PR / Issue / Review 审计工作流现状

[audit-github-style-workflow-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/audit-github-style-workflow-plan.md) 已定义：

- AuditTask 对应 Issue；
- AuditWorkBranch 对应 Branch；
- AuditReviewRequest 对应 Pull Request；
- AuditReviewAction 对应 Review；
- Merge 对应审计结论归档、底稿定稿。

前端菜单 [MainShell.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/layout/MainShell.tsx) 已有：

- 审计任务；
- 复核请求；
- 审计工作底稿；
- 审计工作流。

但支持性文件页面与工作底稿/PR/Issue 流程之间的解释和入口还不够清晰。

## Proposed Changes

### Change 1：更新核心概念文档，冻结新术语边界

文件：

- [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/core-business-concepts-boundary.md)

修改内容：

1. 增加“支持性文件 Supporting File”概念。
2. 明确 `SourceFile` 在用户界面中称为“支持性文件”。
3. 明确支持性文件是不可篡改原件，系统只允许维护元数据：
   - 所属账簿/账簿；
   - 所属项目；
   - 往来单位；
   - 文件类型；
   - 解析状态；
   - 归档分类；
   - 备注/标签。
4. 增加“审计工作底稿 Workpaper”概念。
5. 明确工作底稿是加工成果，承载：
   - 底稿索引；
   - 版本；
   - 审计程序；
   - 任务 Issue；
   - 复核 PR；
   - Review 意见；
   - Merge/归档状态。
6. 补充链路：

```text
支持性文件 SourceFile（原始证据，不可篡改）
  → 解析/识别/分类
  → 模块台账或审计程序
  → 工作底稿 WorkpaperVersion（加工成果，可版本化）
  → 复核请求 AuditReviewRequest（PR）
  → 复核动作 AuditReviewAction（Review）
  → 归档/定稿
```

为什么：

- 防止用户把“原始文件”和“工作底稿”混成一类。
- 符合审计证据保全和工作底稿复核留痕要求。

### Change 2：统一“账簿文件”前端文案为“支持性文件”

文件：

- [LedgerFilesPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/LedgerFilesPage.tsx)
- [MainShell.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/layout/MainShell.tsx)
- [LedgerManagementPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/LedgerManagementPage.tsx)

修改内容：

1. 菜单“账簿文件”改为“支持性文件”。
2. 页面标题“账簿文件”改为“支持性文件”。
3. 页面说明改为：

```text
支持性文件是关联到当前账簿/账簿的原始资料原件，例如合同、发票、银行回单、序时簿、图片、PDF 等。系统仅维护分类、关联、解析状态和归档路径，不应直接篡改原文件内容。
```

4. 编辑按钮文案从“编辑”调整为“编辑元数据”。
5. 删除按钮保留，但二次确认文案强调证据链影响；如执行阶段评估风险较高，可改成“作废/归档”而不是物理删除。

为什么：

- 用户界面直接传递“原件不可篡改”的原则。
- 避免误解为“账簿文件”等同于系统账簿配置文件。

### Change 3：在支持性文件页面增加“账簿 + 项目双绑定”说明和筛选

文件：

- [LedgerFilesPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/LedgerFilesPage.tsx)
- [client.ts](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/api/client.ts)
- 后端文件接口，优先检查 [routes_files.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_files.py)

修改内容：

1. 在支持性文件页面展示当前账簿/账簿。
2. 增加项目归属列的说明：
   - 直接来源：导入任务的 `project_id`；
   - 间接来源：项目绑定账簿 `ProjectLedger`；
   - 归档来源：archive metadata。
3. 如果现有接口已返回 `project_name`，前端优先展示；否则展示“未归类到项目”。
4. 增加“按项目筛选”入口，若后端暂不支持则先只做页面规划，不强行新建复杂关系。

为什么：

- 支持用户理解：支持性文件先属于账簿/账簿，再在审计项目中归类。
- 与用户提出的“账簿 + 项目双绑定”一致。

### Change 4：明确支持性文件不可篡改边界，调整操作含义

文件：

- [LedgerFilesPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/LedgerFilesPage.tsx)
- [routes_files.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_files.py)

修改内容：

1. 前端编辑弹窗标题改为“编辑支持性文件元数据”。
2. 可编辑字段限定为：
   - 文件展示名；
   - 文件类型；
   - 备注；
   - 往来单位；
   - 账簿/账簿归属；
   - 项目归类；
   - 标签/分类。
3. 不允许编辑：
   - 原始文件内容；
   - `storage_path`；
   - 原始哈希；
   - OCR 原文，除非作为“校正文本版本”单独留痕。
4. 如果后端已有文件删除接口，前端提示语改为：

```text
删除支持性文件会影响审计证据链。若该文件已生成工作底稿、台账或凭证草稿，建议使用归档/作废流程，不建议直接删除。
```

为什么：

- 原始支持性文件应保持证据属性。
- 元数据可以纠正，原件不应静默改写。

### Change 5：在工作底稿页面补充“加工成果”说明和支持性文件来源入口

文件：

- [WorkpapersPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/WorkpapersPage.tsx)
- [routes_workpapers.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_workpapers.py)
- [workpaper_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/workpaper_service.py)

修改内容：

1. 页面说明改为：

```text
审计工作底稿是基于支持性文件、审计程序和审计结论加工形成的版本化成果文件。底稿可以提交复核、修订、归档；支持性文件作为原始证据来源保留。
```

2. 在底稿详情版本表中突出 `source_file_id` 和文件名。
3. 增加“查看来源支持性文件”入口。
4. 保持现有“同步归档底稿”能力，但文案调整为“从支持性文件归档生成/同步底稿索引”。

为什么：

- 让用户清楚：工作底稿不是原始证据本身，而是审计加工成果。
- 与 PR / Issue / Review 流程形成闭环。

### Change 6：补充审计工作流说明：Issue / PR / Review 与底稿关系

文件：

- [audit-github-style-workflow-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/audit-github-style-workflow-plan.md)
- [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/core-business-concepts-boundary.md)

修改内容：

1. 增加“支持性文件不是 Issue/PR 的直接对象，工作底稿才进入 PR/Review 流程”的说明。
2. 明确：

```text
支持性文件：证据来源，尽量不可篡改。
审计任务 Issue：要解决的问题或审计程序。
工作分支 Branch：执行底稿编制的隔离工作区。
复核请求 PR：提交底稿和结论等待复核。
复核 Review：复核人员授权认可或要求修改。
Merge：底稿定稿并归档。
```

为什么：

- 避免把每个原始 PDF、发票、合同都直接当作 PR。
- PR 应针对“加工后的底稿和结论”，不是单纯原件。

### Change 7：暂不新增数据库大迁移，只先统一术语和现有关系

本阶段不建议立即做：

- 不把 `SourceFile` 直接改名为 `SupportingFile`。
- 不把 `Ledger` 直接改名为 `Book` 或“账簿”。
- 不强制给 `SourceFile` 新增 `project_id` 字段。
- 不删除 `organization_id` 兼容字段。

原因：

- 现有代码已广泛使用 `SourceFile`、`Ledger`。
- 大规模改名会引入高风险回归。
- 当前 `ImportJob.project_id` + `ProjectLedger` + archive metadata 已可支撑“账簿 + 项目”双绑定解释。

后续如需增强，可以单独规划：

- `SourceFile.project_id` 或 `source_file_projects` 多对多表；
- 文件哈希和不可篡改校验；
- 支持性文件作废/替换/版本链；
- 工作底稿与复核请求强绑定。

## Assumptions & Decisions

1. 技术模型名暂不重命名。
   - `Ledger` 继续作为账簿/核算边界。
   - `SourceFile` 继续作为支持性文件的技术载体。
   - `WorkpaperIndex` / `WorkpaperVersion` 继续作为审计工作底稿载体。

2. 用户界面优先使用更易懂的业务名称。
   - “账簿文件”改为“支持性文件”。
   - “工作底稿库”保持，但补充“加工成果、版本化、复核归档”的说明。

3. 支持性文件不可篡改原则先通过文案和操作边界体现。
   - 本计划不立即引入文件哈希校验和不可变存储。
   - 但后续可作为安全增强独立实现。

4. 项目双绑定先沿用现有结构。
   - 账簿/账簿归属：`SourceFile.ledger_id`。
   - 项目归属：`ImportJob.project_id`、`ProjectLedger`、archive metadata。
   - 不在本次计划中强行新增 `SourceFile.project_id`。

5. 审计工作底稿进入 PR/Issue/Review 流程，支持性文件不直接进入 PR 流程。
   - 支持性文件是证据来源。
   - 工作底稿是复核对象。

## Verification Steps

执行阶段完成后，应按以下步骤验证：

1. 术语验证
   - 打开主导航，确认原“账簿文件”显示为“支持性文件”。
   - 打开支持性文件页面，确认页面说明明确“原始资料原件，不是工作底稿”。
   - 打开审计工作底稿页面，确认说明明确“加工成果、版本化、复核归档”。

2. 支持性文件边界验证
   - 上传合同、发票、银行回单后，文件出现在支持性文件列表。
   - 文件仍按当前账簿/账簿过滤。
   - 可修改元数据，但页面不暗示可以修改原文件内容。
   - 删除/作废提示强调证据链风险。

3. 账簿 + 项目双绑定验证
   - 创建项目并绑定账簿/账簿。
   - 导入文件时关联账簿/账簿和项目。
   - 支持性文件页面能看到或解释项目归类状态。
   - 工作底稿同步后保留 `ledger_id` 和 `project_id` 语义。

4. 工作底稿验证
   - 点击“从支持性文件归档生成/同步底稿索引”。
   - 底稿索引生成后可查看版本。
   - 版本中能追溯来源支持性文件。
   - PR/复核请求页面仍可独立处理复核流程。

5. 回归验证
   - 前端构建通过。
   - 后端导入检查通过。
   - 文件导入、解析引擎、模块台账、工作底稿页面可正常打开。

## Out of Scope

本计划明确不做：

1. 不改正式凭证生成规则。
2. 不改报表计算、结账、损益结转。
3. 不把 AI 解析结果直接变成正式底稿或正式凭证。
4. 不立即做数据库大迁移。
5. 不重命名所有代码中的 `Ledger`、`SourceFile`。
6. 不实现完整文件哈希不可篡改机制。
7. 不实现多级复核的新流程，只承接现有 Review/PR 机制。

## Recommended Execution Order

1. 文档先行：更新核心概念边界和审计工作流说明。
2. UI 术语调整：把“账簿文件”改为“支持性文件”。
3. 支持性文件页面说明和操作边界调整。
4. 工作底稿页面说明和来源支持性文件入口增强。
5. 项目双绑定展示增强。
6. 构建和基础回归验证。
