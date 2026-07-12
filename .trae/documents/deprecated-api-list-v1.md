# Deprecated API 清单 v1

> **生效日期**: 2026-07-06  
> **章程**: [development-convergence-charter.md](./development-convergence-charter.md) 阶段 1  
> **保留策略**: 只读兼容 ≥1 版本周期，**禁止前端新增调用**

## 已标记 deprecated

| 链路 | 前缀 | 替代主路径 | 路由文件 |
|------|------|------------|----------|
| IMP-B | `/api/unified-import` | `/api/import-jobs` | `routes_unified_import.py` |
| IMP-C | `/api/parse/*` | `/api/import-jobs` + `/api/parser-engine` | `routes_document_parsing.py` |

## 主路径（保留）

| 链路 | 前缀 | 用途 |
|------|------|------|
| IMP-A | `/api/import-jobs` | 导入任务中枢 |
| IMP-D | `/api/parser-engine` | 场景 B 运行时与调试 |
| IMP-E | `/api/parser-voucher` | 解析草稿确认 |

## 前端约束

- `frontend/` 内 **不得** 新增对 `unified-import`、`/api/parse/` 的 `fetch`/`request` 调用。
- 存量调用：截至 2026-07-06 扫描为 **0**（仅后端测试 `test_document_parsing_api.py` 使用 `/api/parse`）。
