# API 边界收敛 Phase 2 — 验收清单

> 对应 [spec.md](./spec.md)
> 状态：实施中（2026-08-02）

---

## S2-2：凭证双轨收敛（`/entries/vouchers/*` → deprecated）

- [ ] A1-1 后端 6 端点 OpenAPI `deprecated=True`
- [ ] A1-2 docstring `.. deprecated:: 2026-08-01` + 替代说明
- [ ] A1-3 tags 含 `deprecated:entries-vouchers`（Swagger 自动分组 + 标灰）
- [ ] A1-4 HTTP 响应头 `Deprecation: true` / `Sunset` / `Link`（复用 deprecation 中间件）
- [ ] A1-5 功能行为不变（旧测试仍绿，无代码逻辑变更）
- [ ] A2 client.ts 6 方法 JSDoc `@deprecated`（reviewVoucher / reviewVouchersBatch / unreviewVoucher / queryVouchers / getVoucherLines / deleteVouchersBatch）
- [ ] A6 deprecated-api-list-v1.md 新增 ENTRIES-V1 条目

## S2-4：client.ts 函数名中性化（去除 Engine 暗示）

- [ ] A3-1 `parseImportedSourceFile` 由 alias 转为主名（保持功能同源）
- [ ] A3-2 新增 `getParsingRuntimeStatus` → 调 `/api/parser-engine/status`，旧 `getParserEngineStatus` 为 alias
- [ ] A3-3 新增 `getDocumentParsingConfig` → 调 `/api/config/parser-engine`，旧 `getParserEngineConfig` 为 alias
- [ ] A3-4 新增 `saveDocumentParsingConfig` → 调 `/api/config/parser-engine` POST，旧 `saveParserEngineConfig` 为 alias
- [ ] A3-5 旧调用方不改（兼容到 2027-02-01）；调用方新代码推荐使用新名

## 验证

- [ ] A4 pytest 全绿（目标 ~905，+5 新 deprecated 头测试）
- [ ] A5 tsc 0 错误 + vitest 77/77
- [ ] code-truth-status.md §3.4 「API 边界收敛」行更新 + §2 进度表
