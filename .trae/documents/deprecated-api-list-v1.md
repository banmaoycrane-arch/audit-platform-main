# Deprecated API 清单 v1

> **生效日期**: 2026-07-06  
> **章程**: [development-convergence-charter.md](./development-convergence-charter.md) 阶段 1  
> **保留策略**: 只读兼容 ≥1 版本周期，**禁止前端新增调用**  
> **Phase 3 收口**: 2026-08-01（[api-boundary-governance-plan.md](./api-boundary-governance-plan.md) §五）
> **Phase 4 收口**: 2026-08-01（Tag 服务统一；entries 内嵌 tags 三端点废弃 + 307 重定向到 `/api/entry-tags`）

## 已标记 deprecated

| 链路 | 前缀 | 替代主路径 | 路由文件 | 响应头 |
|------|------|------------|----------|--------|
| IMP-B | `/api/unified-import` | `/api/import-jobs` | `routes_unified_import.py` | `Deprecation: true` + `Sunset` + `Link` |
| IMP-C | `/api/parse/*` | `/api/import-jobs` + `/api/parser-engine` | `routes_document_parsing.py` | `Deprecation: true` + `Sunset` + `Link` |
| **ENTRIES-V1** | `/api/entries/vouchers/*`（6 端点） | `/api/vouchers`（Voucher 聚合根） | `routes_entries.py` | `Deprecation: true` + `Sunset` + `Link`（Phase 2 2026-08-02） |
| TAG-A | `GET /api/entries/{entry_id}/tags` | `GET /api/entry-tags/tags?entry_id=...` | `routes_entries.py` | 307 重定向（Phase 5 印章模式） |
| TAG-A | `POST /api/entries/{entry_id}/tags` | `POST /api/entry-tags/tags` | `routes_entries.py` | 307 重定向（Phase 5 印章模式） |
| TAG-A | `DELETE /api/entries/{entry_id}/tags/{tag_id}` | `DELETE /api/entry-tags/tags/{tag_id}` | `routes_entries.py` | 307 重定向（Phase 5 印章模式） |

### ENTRIES-V1 详细说明（2026-08-02 新增，Phase 2）

- **废弃原因**：AGENTS.md §1.2 要求「Voucher 为聚合根、Entry 为子资源」。
  `/api/entries/vouchers/*` 属「复合键凭证模型」（直接从 AccountingEntry 按 voucher_no+voucher_date 聚合，**无真实 Voucher 表**），
  与 `/api/vouchers`（真实 Voucher 表，使用 Voucher.id 作为主键）双轨并行，
  造成代码重复、测试面扩大、DDD 物理分包受阻。
- **替代路径**：全部走 `/api/vouchers` Voucher 聚合根（创建 / 列表 / 详情 / 更新 / 删除 / 复核 / 入账 / 取消）。
- **不做 307 重定向**：复合键 `(voucher_no, voucher_date)` 与 Voucher.id 非双射（同复合键可能匹配多 voucher.id 或不存在），重定向会破坏复合键查询场景。
- **6 个端点清单**：
  1. `GET /api/entries/vouchers` — list_voucher_cards（按凭证聚合展示）
  2. `GET /api/entries/vouchers/lines` — get_voucher_lines（按复合键展开分录行）
  3. `POST /api/entries/vouchers/batch-delete` — batch_delete_vouchers
  4. `POST /api/entries/vouchers/{voucher_id}/review` — review_voucher_endpoint
  5. `POST /api/entries/vouchers/review-batch` — review_vouchers_batch_endpoint
  6. `POST /api/entries/vouchers/{voucher_id}/unreview` — unreview_voucher_endpoint
- **保留端点**：`PATCH /api/entries/{id}`、`GET /api/entries/{id}`、`POST /api/entries/batch-review` 等纯分录行 API 保留（符合「Entry 为子资源」）。
- **前端约束**：client.ts 中 `queryVouchers` / `getVoucherLines` / `deleteVouchersBatch` / `reviewVoucher` / `reviewVouchersBatch` / `unreviewVoucher` 已加 `@deprecated` JSDoc；存量 3 处调用不强制迁移（功能不等价），新建功能必须使用 `/api/vouchers`。
- **OpenAPI 标注**：6 端点 `deprecated=True` + docstring `.. deprecated:: 2026-08-01` + tags 含 `deprecated:entries-vouchers`，Swagger UI 自动标灰。
- **HTTP 响应头**：Deprecation 中间件命中 `/api/entries/vouchers` 前缀，响应头 `Deprecation: true` + `Sunset: Mon, 01 Feb 2027 00:00:00 GMT` + `Link: </api/vouchers>; rel="successor-version"`。

### TAG-A 详细说明（2026-08-01 新增）

- **废弃原因**: `/api/entries/{id}/tags` 内嵌标签端点与 `/api/entry-tags` 主路径功能重叠；AGENTS.md §1.2 要求「Voucher 为聚合根、Entry 为子资源」，标签应统一走 `entry-tags` 服务。
- **替代路径**: 全部走 `/api/entry-tags`（20 端点 CRUD + 向量同步 + 搜索）。`/api/entries/{id}/tags` 的 GET/POST/DELETE 三端点统一 307 重定向到对应 `/api/entry-tags/tags` 端点，保留 query。
- **保留端点**: `PATCH /api/entries/{entry_id}/tags` 暂保留（前序 spec 决定，用于批量更新分录标签；待 `entry-tags` 扩展 PATCH 后再废弃）。
- **前端约束**: 前端 `client.ts` 早前已全量迁移至 `/api/entry-tags`，无残留调用（2026-08-01 grep 确认）。
- **OpenAPI 标注**: 三端点 `deprecated=True` + docstring `.. deprecated::` + tags 含 `deprecated:entries-tags`，Swagger UI 自动标灰。
- **未补 HTTP 响应头**: 307 重定向端点不直接返回 `Deprecation: true` 等响应头（重定向后由替代路径响应）；与 Phase 5 印章 `compat_router` 模式一致。

## deprecated 标注四重点（每条 deprecated 路由均满足）

1. **OpenAPI `deprecated=True`** — FastAPI Router 构造参数，Swagger UI 自动标灰
2. **docstring `.. deprecated::`** — 模块级 docstring 注明废弃日期与替代路径
3. **tags 注明** — Router tags 含「deprecated」字样
4. **HTTP 响应头**（2026-08-01 Phase 3 补齐）— 中间件 `app/core/deprecation.py`：
   - `Deprecation: true`（IETF draft-ietf-httpapi-deprecation-header）
   - `Sunset: Mon, 01 Feb 2027 00:00:00 GMT`（RFC 8594，计划移除日期）
   - `Link: </api/import-jobs>; rel="successor-version"`（指向替代主路径）

## 主路径（保留）

| 链路 | 前缀 | 用途 |
|------|------|------|
| IMP-A | `/api/import-jobs` | 导入任务中枢 |
| IMP-D | `/api/parser-engine` | 场景 B 运行时与调试 |
| IMP-E | `/api/parser-voucher` | 解析草稿确认 |

## 前端约束

- `frontend/` 内 **不得** 新增对 `unified-import`、`/api/parse/` 的 `fetch`/`request` 调用。
- 存量调用：截至 2026-07-06 扫描为 **0**（仅后端测试 `test_document_parsing_api.py` 使用 `/api/parse`）。
- 客户端可通过响应头 `Deprecation: true` 程序化检测废弃 API，提前迁移至主路径。
