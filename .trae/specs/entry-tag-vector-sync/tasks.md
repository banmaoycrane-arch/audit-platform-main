# Tasks

- [x] Task 1: EntryTag API 扩展
  - [x] SubTask 1.1: 修改 `backend/app/api/routes_entries.py`，让 `GET /api/entries/{entry_id}/tags` 返回完整字段
  - [x] SubTask 1.2: 新增 `POST /api/entries/{entry_id}/tags` 单条创建 tag
  - [x] SubTask 1.3: 新增 `DELETE /api/entries/{entry_id}/tags/{tag_id}` 单条删除 tag
  - [x] SubTask 1.4: 保持现有 `PATCH /api/entries/{entry_id}/tags` 批量替换接口兼容

- [x] Task 2: EntryTag 向量同步服务
  - [x] SubTask 2.1: 新增 `backend/app/services/entry_tag_vector_service.py`
  - [x] SubTask 2.2: 实现 tag 文本拼接：`tag_type + tag_value + tag_name + entry.normalized_text`
  - [x] SubTask 2.3: 实现稳定 point_id：`entry_tag_{tag_id}`
  - [x] SubTask 2.4: Qdrant upsert 成功后将 `vector_pending=false`
  - [x] SubTask 2.5: Qdrant 不可用时返回降级结果，不修改 pending 状态

- [x] Task 3: EntryTag 向量同步 API
  - [x] SubTask 3.1: 新增 `backend/app/api/routes_entry_tags.py`
  - [x] SubTask 3.2: 实现 `POST /api/entry-tags/sync-vector`，支持 `limit` 参数
  - [x] SubTask 3.3: 在 `backend/app/main.py` 注册路由

- [x] Task 4: 测试与文档状态同步
  - [x] SubTask 4.1: 新增 `backend/tests/test_entry_tags_api.py`
  - [x] SubTask 4.2: 覆盖：完整读取、新增、删除、未知分录 404、错误 tag 404、Qdrant 不可用降级
  - [x] SubTask 4.3: 运行相关 pytest
  - [x] SubTask 4.4: 运行后端全量 pytest
  - [x] SubTask 4.5: 运行前端 `npm run lint`
  - [x] SubTask 4.6: 勾选 `auto-generate-entries-from-source/tasks.md` 的 Task 4.3 / 4.4

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 1-3
