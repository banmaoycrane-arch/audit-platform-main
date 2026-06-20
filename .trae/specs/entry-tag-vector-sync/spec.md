# EntryTag 独立 API 与向量同步 Spec

## Why

当前分录标签 `EntryTag` 已经在关系数据库落库，并带有 `vector_pending=true` 标记，但缺少完整的标签 CRUD API 与批量向量同步入口。用户此前明确要求“所有辅助核算都转为 tag，并在关系数据库与向量数据库存储”，因此需要把 tag 从“内部写入字段”升级为可维护、可同步、可审计追踪的正式能力。

## What Changes

- 扩展分录标签 API：
  - `GET /api/entries/{entry_id}/tags` 返回完整 tag 字段
  - `POST /api/entries/{entry_id}/tags` 新增单个 tag
  - `DELETE /api/entries/{entry_id}/tags/{tag_id}` 删除单个 tag
  - 保留兼容现有 `PATCH /api/entries/{entry_id}/tags` 的批量替换能力
- 新增向量同步 API：
  - `POST /api/entry-tags/sync-vector` 同步 `vector_pending=true` 的 tag 到 Qdrant
  - Qdrant 不可用时不阻塞主流程，返回降级提示，保留 `vector_pending=true`
- 新增 service：`entry_tag_vector_service.py`，集中处理 tag 文本拼接、point_id 生成、Qdrant upsert、pending 状态更新。
- 新增测试，覆盖关系库 CRUD 与向量库不可用时的优雅降级。

## Impact

- Affected specs:
  - `auto-generate-entries-from-source`：完成 Task 4.3 / 4.4
  - `summary-library`：Tags 多维度语义标签能力闭环
- Affected code:
  - 修改 `backend/app/api/routes_entries.py`
  - 新增 `backend/app/api/routes_entry_tags.py`
  - 新增 `backend/app/services/entry_tag_vector_service.py`
  - 修改 `backend/app/main.py` 注册路由
  - 新增 `backend/tests/test_entry_tags_api.py`

## ADDED Requirements

### Requirement: EntryTag 完整读取

系统 SHALL 提供 `GET /api/entries/{entry_id}/tags` 返回指定分录的完整标签列表，包括 `id`、`tag_name`、`tag_type`、`tag_value`、`tag_value_normalized`、`tag_source`、`confidence`、`reviewed_by_user`、`vector_pending`、`created_at`。

#### Scenario: 成功读取分录标签
- **WHEN** 调用 `GET /api/entries/{entry_id}/tags`
- **THEN** 返回该分录的全部标签
- **AND** 返回字段包含 `vector_pending`

### Requirement: EntryTag 单条新增

系统 SHALL 提供 `POST /api/entries/{entry_id}/tags` 新增单个标签，并默认将 `vector_pending` 设置为 `true`。

#### Scenario: 新增客户辅助核算 tag
- **WHEN** 向某条分录提交 `{tag_type: "counterparty", tag_value: "供应商A"}`
- **THEN** 系统新增一条 EntryTag
- **AND** `vector_pending` 为 `true`

### Requirement: EntryTag 单条删除

系统 SHALL 提供 `DELETE /api/entries/{entry_id}/tags/{tag_id}` 删除指定分录下的指定标签。

#### Scenario: 删除错误标签
- **WHEN** 删除属于该分录的 tag
- **THEN** 返回 `{deleted: 1}`

#### Scenario: 删除不存在或不属于该分录的标签
- **WHEN** tag 不存在或 entry_id 不匹配
- **THEN** 返回 404

### Requirement: 向量同步入口

系统 SHALL 提供 `POST /api/entry-tags/sync-vector`，批量同步 `vector_pending=true` 的 EntryTag 到 Qdrant。

#### Scenario: Qdrant 可用时同步成功
- **WHEN** 向量库可用，调用同步接口
- **THEN** 已同步 tag 的 `vector_pending` 改为 `false`
- **AND** 返回 synced_count

#### Scenario: Qdrant 不可用时优雅降级
- **WHEN** Qdrant 不可用
- **THEN** 接口返回 200
- **AND** 返回 `vector_available=false`
- **AND** 标签仍保持 `vector_pending=true`

### Requirement: 兼容现有 PATCH 批量替换

系统 SHALL 保留现有 `PATCH /api/entries/{entry_id}/tags` 能力，不破坏已有测试和前端调用。

#### Scenario: 旧接口仍可用
- **WHEN** 调用旧的 PATCH 标签接口
- **THEN** 标签仍可批量替换
- **AND** 新增标签也应标记 `vector_pending=true`

## MODIFIED Requirements

### Requirement: 辅助核算转 Tag（双库）

原要求“关系库写入 + 向量同步 pending 占位”修改为：关系库写入后提供显式同步入口；向量库可用时写入 Qdrant 并清理 pending，不可用时保留 pending 状态并返回降级提示。

## REMOVED Requirements

无。

## 财务视角说明

- `EntryTag` 可以理解为“辅助核算维度”：客户、供应商、项目、税种、业务类型等都不再强行做二级科目，而是作为标签挂到分录上。
- 关系数据库负责“确定性账簿记录”，Qdrant 向量库负责“相似语义检索”。这相当于会计账簿 + 审计检索索引两套账外辅助工具，但最终账务口径仍以关系数据库为准。
- `vector_pending=true` 是一个待办标记，类似“凭证已录入但附件尚未归档”。向量库不可用时不能影响凭证主流程。