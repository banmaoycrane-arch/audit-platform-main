# Checklist

> 对应 [spec.md](./spec.md) §6 验收口径。基线：git `1366f04` / pytest 891 / tsc 0 / vitest 77。完成态：pytest 894 / tsc 0 / vitest 77（2026-08-01）。

## 旧路径兼容
- [x] `GET /api/entries/{entry_id}/tags` 返回 307 重定向到 `/api/entry-tags/tags?entry_id=...`
- [x] `POST /api/entries/{entry_id}/tags` 返回 307 重定向到 `/api/entry-tags/tags`
- [x] `DELETE /api/entries/{entry_id}/tags/{tag_id}` 返回 307 重定向到 `/api/entry-tags/tags/{tag_id}`
- [x] 重定向保留 query 参数
- [x] OpenAPI schema 中三端点 `deprecated: true`

## 向量参数位（DocumentTag）
- [x] `search_similar_tags` 支持 `ledger_id: int | None = None`，默认 None 行为不变
- [x] `sync_pending_tags` 向量 payload 含 `ledger_id` 键（值 None）
- [x] 传入 ledger_id 时不报错（过滤结果与 None 一致，因模型无该字段）
- [x] `/api/document-tags/search`、`/sync-vectors` 端点透传可选 ledger_id

## OpenAPI tag 命名
- [x] `/api/entry-tags` 路由 tags 为 `entry-tags`
- [x] `/api/document-tags` 路由 tags 为 `document-tags`
- [x] 废弃端点 tags 含 `deprecated:entries-tags`

## 前端迁移
- [x] `client.ts` 无对 `/api/entries/{id}/tags` 的调用
- [x] 前端 tsc 0 错误
- [x] 前端 vitest 77/77 通过

## 财务语义不变
- [x] EntryTag 核算字段（weight/reviewed_by_user/category_id/value_id）语义未改
- [x] DocumentTag「不参与借贷平衡」定位未改
- [x] 未合并 EntryTag 与 DocumentTag 表
- [x] 未新增 Alembic 迁移

## 回归
- [x] 后端全量 pytest 通过（≥891）— 2026-08-01 实测 **894/894**
- [x] 新增 redirect 测试 4 个通过
- [x] 新增 ledger_id 参数位回归测试通过

## 文档真值
- [x] `deprecated-api-list-v1.md` 登记三端点
- [x] `api-boundary-governance-plan.md` §五 Phase 4 标记完成
- [x] `code-truth-status.md` P2#12 状态更新 + 串库风险登记 + 后置任务登记
