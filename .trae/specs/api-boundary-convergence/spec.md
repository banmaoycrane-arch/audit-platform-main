# API 边界收敛 Phase 2 — 规格说明

> **所属域**: D12 工程治理（收敛章程 §四阶段 2）
> **治理章程**: [development-convergence-charter.md](../../documents/development-convergence-charter.md)
> **治理计划**: [api-boundary-governance-plan.md](../../documents/api-boundary-governance-plan.md)
> **废弃清单**: [deprecated-api-list-v1.md](../../documents/deprecated-api-list-v1.md)
> **前置已完成**: Phase 0/1/3/4/5/6 ✅
> **状态**: 实施中（2026-08-02）

---

## 一、目标

Phase 2 完成两项收敛行动：

| 编号 | 行动 | 收敛章程引用 |
|------|------|--------------|
| S2-2 | `entries/vouchers/*` 废弃 + `vouchers` 为凭证唯一聚合根 | convergence §四·S2-2 + AGENTS.md §1.2 |
| S2-4 | client.ts 函数名中性化（去除 Engine 暗示） | convergence §四·S2-4 |

**为什么现在做？**（技术决策解释）
- L6 签字未完成时，章程禁止"扩功能"，但允许"修债务"。收敛 API = 减冗余 + 清双轨，是明确的债务工作。
- `entries/vouchers/*`（复合键凭证模型）与 `/vouchers/*`（Voucher.id 模型）是两套完全不同的凭证实现方式；AGENTS.md §1.2 要求「Voucher 为聚合根、Entry 为子资源」，复合键模型本质是「没有 Voucher 表」的历史遗留。双轨并存会导致开发成本翻倍（同一问题两套代码要验证）、测试面扩大、未来 DDD 物理分包受阻。
- client.ts 中 `parseSourceFileWithEngine` 等命名暗示「单一引擎」，与双场景 Charter（场景 A 自适应导入 / 场景 B 原始资料解析 + 登记）冲突。开发者容易误以为"所有解析都走 parser-engine 管理页"，实际是双链路。

---

## 二、In / Out Scope

### In Scope

| # | 子项 | 影响面 |
|---|------|--------|
| 2.1 | `/entries/vouchers`、`/entries/vouchers/lines`、`/entries/vouchers/batch-delete`、`/entries/vouchers/{id}/review`、`/entries/vouchers/review-batch`、`/entries/vouchers/{id}/unreview` 6 端点加 deprecated 四重注明（OpenAPI deprecated=True + docstring .. deprecated:: + tags deprecated:entries-vouchers + Deprecation HTTP 响应头） | 后端 routes_entries.py + tests |
| 2.2 | `/entries/vouchers/*` **不做 307 重定向**：因为复合键（voucher_no+voucher_date）→ Voucher.id 的映射不可靠（同一 voucher_no+voucher_date 可能多 Voucher.id 或不存在）；重定向会破坏复合键场景（如旧查询按复合键展开分录行） | 决策记录 |
| 2.3 | client.ts 6 个 `entries/vouchers` 方法（`reviewVoucher`、`reviewVouchersBatch`、`unreviewVoucher`、`queryVouchers`、`getVoucherLines`、`deleteVouchersBatch`）加 JSDoc `@deprecated` 注释，但**不迁移**（功能不完全等价） | 前端 client.ts |
| 2.4 | client.ts 函数名中性化：`parseSourceFileWithEngine` → `parseImportedSourceFile`（已有 alias，转正）；`getParserEngineStatus` → `getParsingRuntimeStatus`；`getParserEngineConfig` → `getDocumentParsingConfig`；`saveParserEngineConfig` → `saveDocumentParsingConfig`。保留别名到 2027-02-01 做兼容。 | 前端 client.ts（不影响调用方，新增正向名 + 旧名 alias） |
| 2.5 | deprecated-api-list-v1.md 增加 `ENTRIES-V1` 条目（记录 `/entries/vouchers/*` 6 端点废弃） | 文档 |

### Out Scope

| # | 子项 | 原因 |
|---|------|------|
| 2.x | `/entries/vouchers/*` 307 重定向到 `/vouchers/*` | 复合键 → Voucher.id 不可双射 |
| 2.x | VoucherQueryPage / SubsidiaryLedgerPage 的前端调用迁移到 `/vouchers/*` | 功能不等价（查询参数/返回结构不同），迁移会是大重构，P2 后置到 DDD 物理分包阶段 |
| 2.x | 删除 `/entries/vouchers/*` 代码 | 只读兼容 ≥1 版本周期（废弃名单 v1 §保留策略） |
| 2.x | S2-1 `import-jobs` 三 Router 拆分 | 已在 api-boundary-governance §五 Phase 1 标记完成 |
| 2.x | S2-3 对外品牌文案统一（README + 帮助） | 属 S2-3，单独 Sprint |

---

## 三、财务与技术约束（不变）

1. **AGENTS.md §1.2 Voucher 为聚合根**：本 Phase 只标记旧路径 deprecated，不改变任何凭证业务逻辑。
2. **AGENTS.md §2 财务规则**：不触碰过账、结账、损益结转。
3. **只读兼容**：废弃路径功能行为 100% 不变（测试回归验证）。
4. **命名不破坏**：client.ts 中性化时 `parseSourceFileWithEngine` / `parseUploadedFile` / `parseImportedSourceFile` 三者同时存在，互相同源。

---

## 四、验收标准（L3，可程序化验证）

| ID | 验收项 | 验证方法 |
|----|--------|----------|
| A1 | `/entries/vouchers/*` 6 端点均带 `deprecated=True` / tags 含 `deprecated:entries-vouchers` / docstring 含 `.. deprecated::` / HTTP 响应有 `Deprecation: true` | pytest 4–6 个 |
| A2 | client.ts 6 个 entries/vouchers 方法带 `@deprecated` JSDoc | 代码 review |
| A3 | client.ts 新增中性函数：`parseImportedSourceFile`（已存在 alias，转正为主名）、`getParsingRuntimeStatus`、`getDocumentParsingConfig`、`saveDocumentParsingConfig`，旧名做 alias | tsc 0 错误 |
| A4 | pytest 全绿（目标 900 → ~905） | 运行 |
| A5 | tsc 0 错误 + vitest 77/77 | 运行 |
| A6 | deprecated-api-list-v1.md 新增 ENTRIES-V1 条目 | 文档 |

---

## 五、决策树结论（对齐 development-convergence-charter §七）

1. pytest: **900 全绿** ✅
2. L6 双签字：未完成，**只做债务收敛不扩新功能** ✅（本次是减冗余，非扩域）
3. 是否新增第 6 条导入 API：否 ✅
4. 单一解析品牌：client.ts 中性命名推进 ✅
5. DDD 文件：不做物理迁移（P2 冻结） ✅

全部通过 → 可执行本 Phase。
