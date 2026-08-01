# Deprecated API 清单 v1

> **生效日期**: 2026-07-06  
> **章程**: [development-convergence-charter.md](./development-convergence-charter.md) 阶段 1  
> **保留策略**: 只读兼容 ≥1 版本周期，**禁止前端新增调用**  
> **Phase 3 收口**: 2026-08-01（[api-boundary-governance-plan.md](./api-boundary-governance-plan.md) §五）

## 已标记 deprecated

| 链路 | 前缀 | 替代主路径 | 路由文件 | 响应头 |
|------|------|------------|----------|--------|
| IMP-B | `/api/unified-import` | `/api/import-jobs` | `routes_unified_import.py` | `Deprecation: true` + `Sunset` + `Link` |
| IMP-C | `/api/parse/*` | `/api/import-jobs` + `/api/parser-engine` | `routes_document_parsing.py` | `Deprecation: true` + `Sunset` + `Link` |

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
