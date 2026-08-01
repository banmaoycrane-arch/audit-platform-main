# Tasks

> 对应 [spec.md](./spec.md)。基线：git `1366f04` / pytest 891 / tsc 0 / vitest 77。完成态：pytest 894 / tsc 0 / vitest 77（2026-08-01）。

- [x] Task 1: 废弃 entries 内嵌标签端点 + 307 重定向兼容
  - [x] SubTask 1.1: `routes_entries.py` L866-899 三端点（GET/POST `/api/entries/{entry_id}/tags`、DELETE `/api/entries/{entry_id}/tags/{tag_id}`）改为 `compat_router` 307 重定向到 `/api/entry-tags` 对应端点，保留 query
  - [x] SubTask 1.2: 三端点 OpenAPI `deprecated=True` + docstring `.. deprecated::` + tags 注明 `deprecated:entries-tags`
  - [x] SubTask 1.3: 复用 Phase 5 印章 `compat_router` 模式（参照 routes_seals.py 旧路径重定向实现）

- [x] Task 2: DocumentTag 向量服务预留账簿隔离参数位
  - [x] SubTask 2.1: `document_tag_vector_service.search_similar_tags` 增加 `ledger_id: int | None = None` 参数（默认 None，行为不变）
  - [x] SubTask 2.2: `sync_pending_tags` 向量 upsert payload 增加 `ledger_id` 键（值暂 None，因模型无该字段）
  - [x] SubTask 2.3: 检索时若传入 ledger_id 则按 payload filter 过滤（当前过滤结果与 None 一致，不报错）
  - [x] SubTask 2.4: `routes_document_tags.py` 的 `/search`、`/sync-vectors` 端点透传 ledger_id 参数（可选）

- [x] Task 3: OpenAPI tag 命名规范统一
  - [x] SubTask 3.1: `routes_entry_tags.py` router tags 确认为 `entry-tags`；`routes_document_tags.py` router tags 确认为 `document-tags`
  - [x] SubTask 3.2: 废弃端点 tags 含 `deprecated:entries-tags`

- [x] Task 4: 前端迁移
  - [x] SubTask 4.1: `frontend/src/api/client.ts` 中对 `/api/entries/{id}/tags` 的调用迁移到 `/api/entry-tags`
  - [x] SubTask 4.2: grep 确认前端无对旧路径的残留调用

- [x] Task 5: 测试
  - [x] SubTask 5.1: `test_entry_tags_api.py` 新增 4 个 redirect 兼容测试（GET/POST/DELETE 各一 + OpenAPI deprecated 标记）
  - [x] SubTask 5.2: `test_document_tag_service.py` 新增 ledger_id 参数位回归测试（None 兼容 + 传值不报错）
  - [x] SubTask 5.3: 后端全量 pytest 通过（目标 ≥891）— 2026-08-01 实测 **894/894**
  - [x] SubTask 5.4: 前端 tsc 0 错误、vitest 77/77 — 2026-08-01 实测通过

- [x] Task 6: 文档真值同步
  - [x] SubTask 6.1: `deprecated-api-list-v1.md` 登记 `/api/entries/{id}/tags` 三端点 — TAG-A 三行 + 详细说明块
  - [x] SubTask 6.2: `api-boundary-governance-plan.md` §五 Phase 4 补「✅ spec 三件套完成 + 实施完成」
  - [x] SubTask 6.3: `code-truth-status.md` P2#12 状态更新 + DocumentTag 串库风险登记 + 后置任务登记

# Task Dependencies

- Task 3 与 Task 1 同文件可合并提交
- Task 4 依赖 Task 1（旧路径重定向就绪后再迁前端）
- Task 5 依赖 Task 1-4
- Task 6 依赖 Task 5 验收通过
