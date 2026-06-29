# 审计工作底稿协作包实施计划

## Summary

用户补充确认：完整审计工作底稿不只是一个电子表格文件，而应由以下内容共同构成：

```text
电子表格底稿文件
+ Issue / 审计任务
+ Branch / 工作分支
+ PR / 复核请求
+ Review / 复核意见和标记
+ Version / 底稿版本
+ Notification / 协作通知
```

每个底稿都必须经过审核；协作人员应收到通知，知道自己的工作进展、待办事项和复核人员关注点。同时，后台质量审核人员的评论、标记、复核意见不能覆盖或灭失现场人员制作的原始底稿。

本计划在前一份 [workpaper-spreadsheet-implementation-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/workpaper-spreadsheet-implementation-plan.md) 基础上升级，重点是把“电子表格底稿”扩展为“非破坏性的审计底稿协作包”。

核心原则：

1. 现场人员制作的底稿文件作为版本快照保留，不被评论或标记覆盖。
2. 复核人员评论、标记、退回意见作为旁路记录保存。
3. PR / Review 绑定明确的底稿版本，复核的是某个版本，而不是漂浮状态。
4. 通知机制让执行人、复核人、项目经理知道工作进展。
5. 合并/归档只能改变版本状态和归档关系，不直接改写原始支持性文件或现场底稿原版本。

## Current State Analysis

### 1. 当前已有协作骨架

后端模型位于：

- [models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py)

当前已有：

| 实体 | 类 GitHub 概念 | 当前作用 |
|---|---|---|
| `AuditTask` | Issue | 审计任务、问题、待办 |
| `AuditWorkBranch` | Branch | 某任务下的工作分支 |
| `AuditReviewRequest` | Pull Request | 复核请求 |
| `AuditReviewAction` | Review | 复核动作、意见 |
| `AuditComment` | Comment | 评论沟通 |
| `WorkpaperVersion` | 文件版本 | 底稿版本 |

后端服务：

- [audit_task_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_task_service.py)
- [audit_branch_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_branch_service.py)
- [audit_review_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_review_service.py)
- [audit_comment_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_comment_service.py)
- [workpaper_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/workpaper_service.py)

前端页面：

- [AuditTasksPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/AuditTasksPage.tsx)
- [AuditTaskDetailPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/AuditTaskDetailPage.tsx)
- [ReviewRequestsPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/ReviewRequestsPage.tsx)
- [ReviewDetailPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/ReviewDetailPage.tsx)
- [AuditWorkflowPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/AuditWorkflowPage.tsx)
- [WorkpapersPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/WorkpapersPage.tsx)

### 2. 当前评论和复核不会改写底稿原件

当前 `AuditComment` 独立保存：

- `target_type`
- `target_id`
- `content`
- `mention_user_ids`
- `created_by`

评论不会修改：

- `SourceFile`
- `WorkpaperVersion`
- 底稿文件内容

这是正确方向，应继续保持。

### 3. 当前主要缺口

只读探索发现以下缺口：

1. 通知/消息未真正实现。
2. PR/Review 与底稿版本绑定较弱。
3. 合并归档只是状态变更，没有真正固化底稿版本。
4. 前后端状态和动作不一致。
5. 详情页路由参数未正确接入。
6. 评论/标记主要是普通评论，没有底稿单元格/区域级标记。
7. 多级复核字段存在，但服务只实现单级。
8. 复核动作有 `signature_hash` 字段，但未生成。
9. 删除和状态变更留痕不足。

## Proposed Changes

### Change 1：定义“审计底稿协作包”概念

更新文档：

- [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/core-business-concepts-boundary.md)
- [audit-github-style-workflow-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/audit-github-style-workflow-plan.md)

新增定义：

```text
审计工作底稿协作包 = 底稿电子表格文件 + 底稿版本 + 审计任务 + 工作分支 + 复核请求 + 复核意见 + 评论标记 + 通知 + 归档状态。
```

明确：

- Excel 文件是底稿内容载体；
- Issue 是工作任务；
- Branch 是现场人员的工作分支；
- PR 是提交复核的请求；
- Review 是复核人员的意见和授权；
- Comment/Marker 是旁路标注，不改变原文件；
- Merge 是定稿归档动作。

### Change 2：补强 WorkpaperVersion，使其成为电子表格文件快照

文件：

- [models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py#L1737-L1753)
- 新增 Alembic 迁移

建议字段：

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

含义：

- 现场人员制作的 Excel 底稿每次保存或提交都生成一个新版本；
- 旧版本不覆盖；
- 复核人员的意见不写回旧文件；
- 如需修改，应生成新版本。

### Change 3：PR 绑定提交版本，防止复核对象漂移

文件：

- [models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py)
- [audit_review_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_review_service.py)
- [routes_audit_review.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_audit_review.py)

建议为 `AuditReviewRequest` 增加：

```text
submitted_version_id
approved_version_id
merged_version_id
```

规则：

1. 创建 PR 时必须绑定 `submitted_version_id`。
2. 复核通过时记录 `approved_version_id`。
3. 合并归档时记录 `merged_version_id`。
4. 如果 PR 审核期间分支最新版本发生变化，应提示“底稿版本已变化，需要重新提交复核”。

为什么：

- 复核人员审核的是某个确定版本。
- 避免现场人员提交后又改底稿，复核人员看到的版本和归档版本不一致。

### Change 4：评论和标记采用非破坏性旁路记录

当前已有 `AuditComment`，建议扩展或新增 `AuditWorkpaperMarker`。

#### 方案 A：扩展 AuditComment

扩展字段：

```text
marker_type
sheet_name
cell_ref
range_ref
severity
resolved_at
resolved_by
```

#### 方案 B：新增 AuditWorkpaperMarker 表

字段建议：

```text
id
workpaper_version_id
review_request_id
sheet_name
cell_ref
range_ref
marker_type
severity
content
created_by
resolved_by
created_at
resolved_at
```

推荐：第一阶段先扩展 `AuditComment` 支持目标为 `workpaper_version`，并在 `content` 或 metadata 中记录 sheet/cell/range；第二阶段再独立成 `AuditWorkpaperMarker`。

业务规则：

- 标记不修改 Excel 文件；
- 标记显示在预览层；
- 现场人员修改时生成新版本；
- 复核人员的标记保留在原审核版本上。

### Change 5：实现通知/消息机制

新增模型：

```text
AuditNotification
```

建议字段：

```text
id
recipient_user_id
actor_user_id
event_type
target_type
target_id
title
content
is_read
project_id
ledger_id
created_at
read_at
```

新增文件：

- `backend/app/services/audit_notification_service.py`
- `backend/app/api/routes_audit_notifications.py`

触发事件：

| 场景 | 通知对象 |
|---|---|
| 任务分配 | 执行人 |
| 工作分支创建 | 任务负责人/项目经理 |
| 底稿版本提交复核 | 复核人 |
| 复核退回修改 | 提交人/执行人 |
| 复核通过 | 提交人/项目经理 |
| 合并归档 | 项目成员/相关执行人 |
| 评论 @ 某人 | 被提及人员 |
| 标记底稿问题 | 底稿编制人/执行人 |

前端接入：

- [WorkspacePage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/WorkspacePage.tsx) 当前已有通知抽屉占位，可接入真实通知。
- `MainShell` 顶部可显示未读通知角标。

### Change 6：修复前后端状态和动作不一致

涉及文件：

- [ReviewDetailPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/ReviewDetailPage.tsx)
- [AuditTaskDetailPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/AuditTaskDetailPage.tsx)
- [AuditTasksPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/AuditTasksPage.tsx)
- [audit_workflow.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/schemas/audit_workflow.py)

统一口径：

Review action：

```text
approve
request_changes
comment
rework
```

Review status：

```text
draft
review
changes_requested
approved
merged
closed
```

Task status：

```text
open
todo
in_progress
review
closed
rejected
```

Task priority：

```text
high
normal
low
```

### Change 7：修复详情页路由参数

文件：

- [AuditTaskDetailPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/AuditTaskDetailPage.tsx)
- [ReviewDetailPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/ReviewDetailPage.tsx)
- [AuditTasksPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/AuditTasksPage.tsx)
- [ReviewRequestsPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/Audit/ReviewRequestsPage.tsx)

修改：

- 详情页使用 `useParams()` 读取 `taskId` / `reviewId`。
- 列表页点击详情时跳转真实 URL。
- 不再默认加载 ID 1。

为什么：

- 每个底稿协作包必须能从通知、任务、PR 跳到准确对象。

### Change 8：任务状态变更、复核动作、合并归档生成活动流

新增或规划模型：

```text
AuditActivity
```

字段：

```text
id
project_id
ledger_id
actor_user_id
event_type
target_type
target_id
summary
metadata
created_at
```

事件：

- task_created
- task_assigned
- task_status_changed
- branch_created
- workpaper_version_linked
- review_submitted
- review_approved
- review_changes_requested
- comment_created
- marker_created
- review_merged

第一阶段如果不建新表，可先复用 `AuditComment` 记录状态变更说明；但正式方案建议独立活动流。

### Change 9：合并归档不改写旧底稿，只固化版本状态

文件：

- [audit_review_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/audit_review_service.py)
- [workpaper_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/workpaper_service.py)

规则：

1. PR 必须是 `approved` 才能合并。
2. PR 必须有 `approved_version_id`。
3. 合并时将该版本状态改为 `reviewed` 或 `archived`。
4. 记录 `merged_version_id`。
5. 分支状态改为 `merged`。
6. 任务状态改为 `closed`。
7. 不修改旧版本文件内容。
8. 不修改原始支持性文件。

### Change 10：多级复核后置，但字段和流程预留

当前模型有三级复核字段，但服务只实现一级。

第一阶段：

- 保持单级复核；
- 页面清楚显示“当前为一级复核”；
- 不假装三级复核已经完整可用。

第二阶段：

- 实现一级 → 二级 → 三级流转；
- 每级写入独立 `AuditReviewAction`；
- 每级通知对应复核人；
- 最后一级通过后才 `approved`。

## Workflow Design

### 标准底稿协作流程

```text
1. 项目经理创建 Issue / 审计任务
2. 分配现场人员
3. 现场人员创建 Branch / 工作分支
4. 现场人员编制电子表格底稿，生成 WorkpaperVersion v1.0
5. 现场人员提交 PR / 复核请求，绑定 v1.0
6. 系统通知复核人员
7. 复核人员查看 v1.0，添加评论和标记
8. 如果退回：PR = changes_requested，通知现场人员
9. 现场人员根据意见修改，生成 v1.1，不覆盖 v1.0
10. 重新提交 PR，绑定 v1.1
11. 复核通过：记录 approved_version_id
12. 合并归档：v1.1 标记 reviewed/archived，Branch = merged，Issue = closed
```

### 非破坏性原则

```text
现场人员底稿 v1.0：保留
复核人员评论/标记：旁路保存
现场人员修改后 v1.1：新增版本
复核通过版本：明确记录
归档版本：明确记录
原始支持性文件：不改写
```

## Assumptions & Decisions

1. 评论和标记不写回 Excel 原文件。
2. 修改底稿必须生成新版本。
3. PR 必须绑定明确版本。
4. 通知必须可追踪到具体任务、PR、底稿版本或评论。
5. 第一阶段只做单级复核闭环，不假装多级复核完成。
6. 合并归档只固化版本状态，不覆盖旧文件。
7. 支持性文件永远是原始证据来源，不被工作底稿评论影响。

## Verification Steps

### 协作流验证

1. 创建审计任务。
2. 分配给现场人员。
3. 现场人员收到通知。
4. 创建工作分支。
5. 关联或生成底稿版本。
6. 提交复核请求。
7. 复核人收到通知。
8. 复核人添加评论/标记。
9. 现场人员收到通知。
10. 现场人员修订，生成新版本。
11. 复核通过。
12. 合并归档。
13. 检查旧版本仍存在，新版本成为归档版本。

### 非破坏性验证

1. 评论后下载原底稿版本，确认文件未被改写。
2. 标记后检查 `WorkpaperVersion.file_hash` 不变。
3. 修订后产生新版本，旧版本状态不应消失。
4. 复核退回不应改写底稿文件，只产生 ReviewAction 和通知。

### 通知验证

1. 任务分配产生通知。
2. 提交复核产生通知。
3. 退回修改产生通知。
4. 评论 @ 人产生通知。
5. 通知可标记已读。
6. 通知可跳转到具体任务/PR/底稿版本。

## Out of Scope

本计划明确不做：

1. 不做完整在线 Excel 编辑器。
2. 不做多级复核完整实现，只预留。
3. 不改正式凭证、报表、结账。
4. 不让复核评论覆盖现场人员底稿。
5. 不让后台质控标记直接修改原始支持性文件。
6. 不把所有历史底稿一次性迁移为新协作包。

## Recommended Execution Order

1. 修正前后端状态和详情页路由参数。
2. 补通知模型和通知 API。
3. 补任务/PR/评论触发通知。
4. 扩展 WorkpaperVersion 文件快照字段。
5. PR 绑定 submitted_version_id / approved_version_id / merged_version_id。
6. 合并归档时固化版本状态。
7. WorkpapersPage 展示“底稿协作包”：文件版本、任务、分支、PR、评论、通知。
8. 后续增加底稿区域/单元格级标记。

## Final Recommendation

完整审计底稿应定义为：

> **以电子表格文件为主体、以 Issue/Branch/PR/Review 为协作过程、以版本和通知为留痕机制的非破坏性底稿协作包。**

这比单纯“上传一个 Excel 文件”更符合审计底稿的复核、归档和质量控制要求。
