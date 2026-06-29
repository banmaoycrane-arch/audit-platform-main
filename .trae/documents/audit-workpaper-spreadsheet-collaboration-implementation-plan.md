# 审计工作底稿电子表格与 PR/Issue 协作包实施计划

## 1. 需求归属与边界

```text
Domain: D06 审计证据与审计流程
Status: active-increment
Owner Spec: audit-workpaper-collaboration-package-plan / 本计划作为其执行细化
Depends On:
  - D02 团队、账簿/账簿、项目、上下文
  - D05 原始资料导入与解析
  - D03 Shell、导航、工作台、模块入口
Acceptance Level: L6（前后端闭环 + 构建/导入验证 + 可按真实审计流程试用）
```

### In Scope（本次做什么）

1. 明确并落地三类对象的边界：
   - **账簿 / Ledger**：一个会计主体的核算数据边界。
   - **支持性文件 / SourceFile**：合同、发票、回单、银行流水等不可随意篡改的原始证据。
   - **审计工作底稿 / Workpaper**：现场人员加工后的审计文件，包含电子表格文件、版本、Issue、Branch、PR、Review、评论标记、通知、归档状态。
2. 以电子表格文件为底稿主载体：
   - 底稿版本记录文件名、扩展名、存储路径、哈希、大小、Sheet 数、模板编码、工作簿元数据。
   - 使用后端现有 `openpyxl` / 文件快照能力，先不引入完整在线 Excel 编辑器。
3. 完成非破坏性协作链路：
   - 支持性文件不被复核评论覆盖。
   - 评论、标记、复核意见旁路保存。
   - 修改底稿必须形成新版本。
   - PR 必须绑定明确底稿版本。
   - 合并归档只固化版本状态，不覆盖历史版本。
4. 完成前端协作入口闭环：
   - 任务详情、复核详情使用真实路由 ID，不默认加载错误记录。
   - 任务列表、复核列表点击后进入详情页。
   - 工作底稿库展示“底稿协作包”而不是只展示普通文件目录。
   - 审计通知能展示未读、标记已读，并能跳转到任务 / PR / 底稿版本。

### Out of Scope（本次不做什么）

1. 不做完整在线 Excel 编辑器，不实现类似 WPS/Excel 网页内单元格编辑。
2. 不做多级复核完整流转；本次保留模型字段，但执行单级复核闭环。
3. 不重构整个导航系统；顶部多页签工作区另属 D03，可后续单独实施。
4. 不改报表、凭证、结账、基础资料等会计主流程。
5. 不把 AI 作为正式复核结论；AI 只能辅助提示，正式底稿仍由人工编制与复核确认。

## 2. 当前状态分析

### 2.1 已有后端基础

调研确认以下结构已存在：

- 后端模型：[models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py)
  - `SourceFile`：原始支持性文件。
  - `WorkpaperIndex`：底稿索引。
  - `WorkpaperVersion`：底稿版本。
  - `AuditTask`：审计任务 / Issue。
  - `AuditWorkBranch`：工作分支 / Branch。
  - `AuditReviewRequest`：复核请求 / PR。
  - `AuditReviewAction`：复核动作 / Review。
  - `AuditComment`：评论与底稿标记。
  - `AuditNotification`：审计协作通知。

- 工作底稿服务：[workpaper_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/workpaper_service.py)
  - 已支持底稿索引、版本注册、修订、状态更新、目录导出。
  - 当前 `_create_version()` 主要写 `source_file_id`、`version_no`、`status`、`prepared_by`、`change_reason`，尚未充分填充新增的文件快照字段。

- 复核服务：[audit_review_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_review_service.py)
  - 已有 `draft → review → approved/changes_requested → merged` 的主流程。
  - 已要求 PR 绑定 `submitted_version_id`。
  - 已在合并时把通过版本固化为 `reviewed`。

- 通知服务与 API：
  - [audit_notification_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_notification_service.py)
  - [routes_audit_notifications.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_audit_notifications.py)
  - 后端已有任务分配、复核提交、复核通过、退回、合并、评论提及等通知能力。

### 2.2 已有前端基础

- 工作底稿库：[WorkpapersPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/WorkpapersPage.tsx)
  - 当前能展示底稿索引、版本列表、同步归档底稿、导出目录。
  - 还没有清晰展示 Issue、Branch、PR、Review、通知与底稿版本的协作关系。

- 任务详情：[AuditTaskDetailPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/AuditTaskDetailPage.tsx)
  - 已引入 `useParams`，但仍存在 `currentTaskId = taskId || 1`，会导致路由进入时可能默认加载 ID 1。
  - 已有任务状态操作、分支列表、复核请求列表、评论列表。

- 复核详情：[ReviewDetailPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/ReviewDetailPage.tsx)
  - 已显示提交版本、通过版本、归档版本。
  - 状态和动作已基本向后端口径靠拢。

- 前端 API：[client.ts](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/api/client.ts)
  - 已有审计任务、分支、复核请求、评论、通知类型和 API 调用。

### 2.3 主要缺口

1. **术语缺口**：前端仍有“账簿文件”命名，需逐步调整为“支持性文件”。
2. **文件快照缺口**：`WorkpaperVersion` 已有文件快照字段，但服务和 API 还未完整写入和返回。
3. **前端路由缺口**：任务详情和复核详情路由未完全闭环，列表页仍有弹窗或提示式查看。
4. **协作包展示缺口**：工作底稿库只像“目录”，还不像“底稿协作包”。
5. **通知 UI 缺口**：后端通知已实现，前端未形成清晰入口。
6. **审计留痕风险**：评论/文件/任务存在硬删除入口，后续应谨慎处理；本次先不扩大到全部删除治理。
7. **迁移风险**：当前存在两个 `0014` Alembic 迁移文件，执行迁移时可能出现多头迁移，需要验证并按实际情况处理。

## 3. 业务口径定义

### 3.1 账簿 / Ledger

账簿在用户理解上是“具体会计主体核算范围的数据源”。技术上当前对应 `Ledger`，用于界定凭证、期间、报表、审计范围的主过滤口径。

本次实现不重命名数据库实体，避免大规模破坏性变更；前端文案可在适合位置解释为：

```text
账簿：一个会计主体或核算范围的数据边界。
```

### 3.2 支持性文件 / SourceFile

原“账簿文件”建议调整为“支持性文件”。

业务定义：

```text
支持性文件是原始证据载体，例如合同、发票、银行回单、客户供应商资料等。
它必须关联到账簿；进入审计项目后，再关联到项目，形成“账簿 + 项目”双绑定。
支持性文件原则上不可被复核意见直接覆盖或篡改。
```

技术落点：

- 继续使用 `SourceFile` 表。
- 前端 `/ledger/files` 文案从“账簿文件”调整为“支持性文件”。
- 文件修改只修改元数据，不把复核意见写回原始文件内容。

### 3.3 审计工作底稿 / Workpaper

业务定义：

```text
审计工作底稿是现场人员在支持性文件基础上加工形成的审计成果。
完整底稿 = 电子表格文件 + 版本 + Issue + Branch + PR + Review + 评论/标记 + 通知 + 归档状态。
```

与支持性文件的区别：

| 对象 | 性质 | 是否加工 | 是否可版本化 | 是否承载 PR/Issue 流程 |
|---|---|---|---|---|
| 支持性文件 | 原始证据 | 否 | 原则上不改原件 | 否 |
| 审计工作底稿 | 审计成果 | 是 | 是 | 是 |

## 4. 拟实施改动

### 4.1 后端：补齐底稿版本文件快照

涉及文件：

- [workpaper_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/workpaper_service.py)
- [routes_workpapers.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_workpapers.py)
- [client.ts](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/api/client.ts)

计划：

1. 在创建 `WorkpaperVersion` 时，从 `SourceFile` 填充：
   - `file_name`
   - `file_ext`
   - `mime_type` / `file_type`
   - `storage_path`
   - `file_size`
   - `file_hash`
   - `generated_from`
2. 对 `.xlsx` 文件尽量读取：
   - `sheet_count`
   - `workbook_metadata.sheets`
3. API 响应返回这些字段，前端类型同步补齐。

为什么：

- 审计复核应锁定“哪一个文件版本”，而不仅是一个抽象版本号。
- 哈希和大小用于证明复核文件未被静默替换。

### 4.2 后端：修正 PR 与底稿版本的一致性保护

涉及文件：

- [audit_review_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_review_service.py)
- [routes_audit_review.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_audit_review.py)

计划：

1. 保持 `submitted_version_id` 为 PR 必填业务条件。
2. 复核通过时写入 `approved_version_id`。
3. 合并归档时写入 `merged_version_id`，并固化对应 `WorkpaperVersion.status = reviewed`。
4. 如果分支最新版本已变化，要求重新提交 PR。
5. 暂不实现多级复核，前端文案标注“当前版本为单级复核”。

为什么：

- 审计复核人员认可的是某个明确版本，而不是动态变化的文件。
- 退回修改后必须生成新版本，避免复核意见和文件内容错配。

### 4.3 后端：通知触发与查询保持闭环

涉及文件：

- [audit_notification_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_notification_service.py)
- [audit_task_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_task_service.py)
- [audit_review_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_review_service.py)
- [audit_comment_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_comment_service.py)
- [routes_audit_notifications.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_audit_notifications.py)

计划：

1. 保留已有事件类型：
   - `task_assigned`
   - `review_submitted`
   - `review_approved`
   - `review_changes_requested`
   - `review_merged`
   - `comment_mentioned`
   - `workpaper_marker_mentioned`
2. 如发现任务状态变更未通知，补充最小通知逻辑。
3. 不做复杂消息中心；只做审计协作通知的读取、未读数、标记已读和目标跳转。

为什么：

- 底稿协作不是单人文件夹管理，而是多人分工、提交、复核、退回、归档的流程。

### 4.4 前端：修复任务和复核详情路由

涉及文件：

- [AuditTaskDetailPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/AuditTaskDetailPage.tsx)
- [AuditTasksPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/AuditTasksPage.tsx)
- [ReviewRequestsPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/ReviewRequestsPage.tsx)
- [ReviewDetailPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/ReviewDetailPage.tsx)

计划：

1. `AuditTaskDetailPage` 统一使用 `effectiveTaskId`，删除默认 `1` 的逻辑。
2. 如果 URL 无效，显示“任务 ID 无效”，不请求默认任务。
3. `AuditTasksPage` 的“查看详情”跳转到 `/audit/tasks/:taskId`。
4. `ReviewRequestsPage` 的“查看详情”跳转到 `/audit/review-requests/:reviewId`。
5. 统一状态显示：
   - 任务：`open/todo/in_progress/review/closed/rejected`
   - 任务优先级：`high/normal/low`
   - 复核：`draft/review/changes_requested/approved/merged/closed`
   - 复核动作：`approve/request_changes`

为什么：

- PR、Issue、底稿版本都需要稳定 URL，方便通知跳转和复核追踪。

### 4.5 前端：工作底稿库展示“协作包”

涉及文件：

- [WorkpapersPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/WorkpapersPage.tsx)
- [client.ts](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/api/client.ts)

计划：

1. 页面说明改为：
   - “工作底稿是加工后的审计成果，不等同于支持性文件原件”。
2. 版本列表增加展示：
   - 文件名
   - 文件类型
   - 文件大小
   - Sheet 数
   - 文件哈希短码
   - 生成来源
3. 在底稿详情区增加协作链路提示：
   - 关联任务（Issue）
   - 工作分支（Branch）
   - 复核请求（PR）
   - 复核状态
4. 如果后端暂未提供某些关联列表，前端先用已有 `AuditTask`、`AuditWorkBranch`、`AuditReviewRequest` API 按 `workpaper_index_id`、`submitted_version_id` 做最小查询或展示占位。

为什么：

- 用户需要看到“一个底稿不是单个 Excel 文件”，而是可复核、可退回、可归档的协作包。

### 4.6 前端：审计通知入口

涉及文件：

- [MainShell.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/layout/MainShell.tsx)
- [client.ts](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/api/client.ts)
- 可新增或复用现有审计页面组件，尽量不新建大型模块。

计划：

1. 在主界面增加审计通知入口或在审计协作台增加通知卡片。
2. 展示：
   - 未读数量
   - 通知标题
   - 通知内容
   - 创建时间
   - 是否已读
3. 支持：
   - 标记单条已读
   - 全部标记已读
   - 点击跳转：
     - `task` → `/audit/tasks/:id`
     - `review_request` → `/audit/review-requests/:id`
     - `workpaper_version` → `/audit/workpapers` 并提示版本 ID
     - `branch` → 先跳任务详情或工作底稿页，后续再细化

为什么：

- 复核意见、退回修改、@ 提及如果没有通知入口，协作链路就不闭环。

### 4.7 前端：术语调整为“支持性文件”

涉及文件：

- [LedgerFilesPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/LedgerFilesPage.tsx)
- [MainShell.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/layout/MainShell.tsx)

计划：

1. 页面标题、菜单文案从“账簿文件”调整为“支持性文件”。
2. 页面说明增加一句：
   - “支持性文件是合同、发票、回单等原始证据，需先归属账簿；进入审计项目后再形成账簿 + 项目双绑定。”
3. 本次不改数据库字段名，避免破坏现有接口。

为什么：

- 用户已明确“账簿文件”容易误解，应称为“支持性文件”。
- 技术字段可以保持 `SourceFile`，界面语言先贴近审计实务。

## 5. 执行顺序

1. 修正前端详情路由和状态枚举。
2. 补齐底稿版本文件快照字段的写入、返回和前端类型。
3. 完成 PR 版本绑定、复核通过、合并归档的一致性验证。
4. 接入审计通知前端入口。
5. 增强工作底稿库“协作包”展示。
6. 调整“账簿文件”为“支持性文件”的界面文案。
7. 运行构建、导入检查和相关测试。

## 6. 验证步骤

### 6.1 后端验证

1. 运行后端导入检查，确认新增模型、服务、路由可正常导入。
2. 检查 Alembic 当前 heads；如出现多头迁移，按最小方式处理迁移链路。
3. 针对审计协作流程做最小接口验证：
   - 创建任务。
   - 创建或关联底稿版本。
   - 创建工作分支。
   - 创建 PR 并绑定底稿版本。
   - 提交复核。
   - 复核通过或退回。
   - 合并归档。
   - 查询通知。

### 6.2 前端验证

1. 运行 `pnpm.cmd build:frontend`。
2. 页面验证路径：
   - `/ledger/files`：显示“支持性文件”。
   - `/audit/workpapers`：能看到底稿版本和协作包信息。
   - `/audit/tasks`：点击任务进入 `/audit/tasks/:taskId`。
   - `/audit/tasks/:taskId`：不再默认加载 ID 1。
   - `/audit/review-requests`：点击 PR 进入 `/audit/review-requests/:reviewId`。
   - 通知入口：能看到未读通知、标记已读、点击跳转。

### 6.3 财务 / 审计口径验收

1. 支持性文件作为原件，不因复核意见被覆盖。
2. 工作底稿作为加工成果，可以有多个版本。
3. PR 绑定明确底稿版本，复核人员认可的是固定版本。
4. 退回修改不会灭失现场人员原始版本。
5. 合并归档后能看到：
   - 谁编制；
   - 谁复核；
   - 复核意见；
   - 对应版本；
   - 相关通知；
   - 最终归档状态。

## 7. 关键技术解释

- **为什么不直接引入完整在线 Excel 编辑器**：完整在线表格依赖复杂，会引入权限、协同编辑、公式兼容和文件损坏风险。本阶段先把 `.xlsx` 作为可版本化文件管理，先跑通审计复核主流程。
- **为什么 PR 必须绑定底稿版本**：复核人员确认的是某个时点的底稿内容。如果底稿后来被改了，原复核意见不能自动适用于新内容。
- **为什么评论和标记旁路保存**：复核意见属于审计过程记录，不应直接写回或覆盖现场人员制作的原始底稿文件。
- **为什么支持性文件和工作底稿分开**：支持性文件是证据原件；工作底稿是审计人员加工、测试、判断后的成果。两者混在一起会影响证据链和复核责任认定。
