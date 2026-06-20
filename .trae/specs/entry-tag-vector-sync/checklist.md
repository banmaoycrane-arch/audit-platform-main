# Checklist

- [x] `GET /api/entries/{entry_id}/tags` 返回完整 tag 字段
- [x] `POST /api/entries/{entry_id}/tags` 能新增 tag，并设置 `vector_pending=true`
- [x] `DELETE /api/entries/{entry_id}/tags/{tag_id}` 能删除指定 tag
- [x] 旧的 `PATCH /api/entries/{entry_id}/tags` 仍可批量替换
- [x] `entry_tag_vector_service.py` 能生成稳定 point_id
- [x] Qdrant 可用时同步后 `vector_pending=false`
- [x] Qdrant 不可用时接口 200，返回 `vector_available=false`，pending 保持 true
- [x] `POST /api/entry-tags/sync-vector` 已注册并可调用
- [x] `backend/tests/test_entry_tags_api.py` 覆盖主要场景
- [x] 后端全量 pytest 通过
- [x] 前端 `npm run lint` 通过
- [x] `auto-generate-entries-from-source/tasks.md` 中 Task 4.3 / 4.4 已勾选
