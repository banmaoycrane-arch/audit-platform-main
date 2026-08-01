# API 边界收敛 Phase 2 — 任务清单

> 对应 [spec.md](./spec.md) + [checklist.md](./checklist.md)
> 状态：实施中（2026-08-02）

---

## 后端任务（routes_entries.py + tests）

- [ ] T1 `routes_entries.py` 顶部定义子 Router（或用 FastAPI `deprecated` + tags 参数），为 6 个 `/entries/vouchers/*` 端点加 deprecated 四重注明：
  - [ ] `GET /entries/vouchers`（list_voucher_cards）
  - [ ] `GET /entries/vouchers/lines`（get_voucher_lines）
  - [ ] `POST /entries/vouchers/batch-delete`（batch_delete_vouchers）
  - [ ] `POST /entries/vouchers/{voucher_id}/review`
  - [ ] `POST /entries/vouchers/review-batch`
  - [ ] `POST /entries/vouchers/{voucher_id}/unreview`
  四重注明 = OpenAPI `deprecated=True` + docstring `.. deprecated:: 2026-08-01` + tags 含 `deprecated:entries-vouchers` + Deprecation HTTP 响应头（中间件会打）
- [ ] T2 新增 5 个测试：6 端点均可返回 2xx 且响应头含 `Deprecation: true`（功能行为不变，只测 header + deprecated tag 存在）

## 前端任务（client.ts + 调用方无变化）

- [ ] T3 client.ts 中 6 个 `/entries/vouchers/*` 方法加 JSDoc `@deprecated`
- [ ] T4 `parseSourceFileWithEngine` → `parseImportedSourceFile` 主名（alias 已有，互换定义）
- [ ] T5 新增 `getParsingRuntimeStatus` / `getDocumentParsingConfig` / `saveDocumentParsingConfig`，旧名作为 alias 保留

## 文档 + 验证

- [ ] T6 `deprecated-api-list-v1.md` 新增 ENTRIES-V1 条目
- [ ] T7 pytest 全绿 + tsc 0 + vitest 77/77
- [ ] T8 `code-truth-status.md` §2 Phase 2 标记为进行中/完成
