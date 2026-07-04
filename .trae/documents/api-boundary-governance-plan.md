# API 边界治理计划

> **文档类型**: 架构治理与执行计划  
> **创建日期**: 2026-07-04  
> **状态**: active-planning（待评审后进入执行）  
> **用途**: 登记当前后端 API 规模、重叠关系与收敛路线，避免继续新增等价入口

---

## Summary

本计划用于治理当前 `backend/app/api/routes_*.py` 中 API 数量偏多、前缀混挂、业务链路并行等问题。

本计划属于：

```text
Domain: D05（原始资料导入与解析）+ D04（凭证生命周期）+ D12（工程治理）
Status: planning
Owner Spec: api-boundary-governance-plan（本文档）
Depends On: AGENTS.md, requirements-boundary-governance-plan.md, module-refactoring-plan.md
In Scope: API 盘点、重叠识别、保留/废弃/合并决策、分阶段收敛任务
Out of Scope: 立即删除代码、修改财务业务规则、前端页面大改
Acceptance Level: 文档可指导后续 spec 与 PR；执行后 OpenAPI 主路径唯一、deprecated 有清单
```

**治理优先级**（冲突时按此顺序）：

1. `AGENTS.md` — 财务规则、术语、角色边界、任务治理、**§九 API 设计与边界原则**
2. `requirements-domain-index.md` — 需求域归属与 spec 状态
3. 本文档 — API 路径收敛与 deprecated 清单
4. 各 `.trae/specs/*/spec.md` — 具体增量实现

本计划不直接修改业务代码；执行阶段须拆成独立 spec 或 PR，每步可独立验证。所有 API 收敛决策须符合 `AGENTS.md` 第一节术语与第二节财务规则。

---

## 一、当前 API 规模（2026-07-04 静态扫描）

| 指标 | 数量 |
|------|------|
| 路由模块 `routes_*.py` | **53** |
| `main.py` 注册 Router | **53** |
| HTTP 端点（`@router.*`） | **约 366** |
| 系统端点（`/`, `/health`） | **2** |
| **合计** | **约 368** |
| 独立 URL 前缀 `/api/...` | **约 49 组** |

### 1.1 按业务域分布

| 业务域 | 模块数 | 端点约数 | 主要前缀 |
|--------|--------|----------|----------|
| 身份与权限 | 2 | 10 | `/api/auth`, `/api/super-admin` |
| 组织/账簿/项目 | 9 | 69 | `/api/teams`, `/api/projects`, `/api/ledgers`… |
| 记账与报表 | 12 | 91 | `/api/vouchers`, `/api/entries`, `/api/reports`… |
| **导入与解析** | **10** | **59** | `/api/import-jobs`, `/api/parser-engine`, `/api/parse`… |
| 审计协作 | 15 | 72 | `/api/audit/*`, `/api/workpapers`, `/api/audit-tests` |
| 标签/向量/分析 | 3 | 41 | `/api/entry-tags`, `/api/document-tags` |
| AI/配置 | 3 | 29 | `/api/agent`, `/api/config`, `/api/llm-resolution` |
| 其他 | 2 | 4 | `/api/dashboard`, `/api/v1`（印章） |

**结论**: MVP 阶段 API 数量偏多；导入/解析、记账、审计三块端点最多，重叠最集中。

---

## 二、结构性问题（前缀层）

### 2.1 同一 prefix 多 Router 混挂

| 共用前缀 | 挂载模块 | 端点数 | 问题 |
|----------|----------|--------|------|
| **`/api/import-jobs`** | `routes_imports` + `routes_entry_generation` + `routes_export` | 20 | 导入、生成分录、导出/post 混在同一前缀 |
| **`/api/audit-tests`** | `routes_audit_tests` + `routes_audit_export` | 5 | 测试运行与报告导出混挂 |

### 2.2 命名规范不一致

| 问题 | 示例 |
|------|------|
| 印章 API 使用 `/api/v1` | 与其他 `/api/{domain}` 不一致 |
| 泛化词复用 | `review` / `report` / `dashboard` 跨多域出现 |

---

## 三、功能重叠识别（按严重度）

### 🔴 P0 — 导入 / 解析：5 条并行链路

| 链路 ID | 前缀 | 端点约数 | 职责 |
|---------|------|----------|------|
| **IMP-A** | `/api/import-jobs` | 14+6 | 建任务、上传、process、draft、report |
| **IMP-B** | `/api/unified-import` | 3 | 另一套 job/upload/result |
| **IMP-C** | `/api/parse` | 4 | 按类型 contract/invoice/bank/inventory |
| **IMP-D** | `/api/parser-engine` + `/corrections` | 15 | parse-file、质量看板、修正规则 |
| **IMP-E** | `/api/parser-voucher` | 3 | parse-to-drafts、confirm-drafts |

**重叠表现**:

- 「解析文件」:`import-jobs/.../parse`、`parser-engine/parse-file`、`parse/{type}`、`parser-voucher/parse-to-drafts`
- 「生成草稿/分录」:`import-jobs/.../process`、`generate-entries`、`parser-voucher/confirm-drafts`
- 「配置 vs 运行」:`/api/config/parser-engine/*` 与 `/api/parser-engine/*` 边界不清

**目标主路径（建议保留）**: IMP-A + IMP-D + IMP-E  
**建议 deprecated**: IMP-B、IMP-C（或仅保留只读兼容层）

---

### 🔴 P0 — 凭证：`entries` 与 `vouchers` 双轨

> **AGENTS.md 术语依据**（§1.2）：`Accounting Entry` 是最小记账单位；`Voucher` 由若干分录组成且借贷必须平衡。API 设计应反映「凭证为聚合根、分录为子资源」，而非两套平行「凭证查询树」。

| 能力 | `/api/vouchers`（8） | `/api/entries`（16） |
|------|----------------------|----------------------|
| 凭证列表/查询 | ✅ | ⚠️ 重复 `/entries/vouchers` |
| 凭证创建 | ✅ | ❌（走 import/generation） |
| 复核/过账 | ✅ post | ✅ review、batch-review |
| 分录行 CRUD | 嵌在 voucher 内 | ✅ 独立 entry 操作 |

**目标主路径（建议保留）**:

- `/api/vouchers` — 凭证级 CRUD、入账（post）、期间校验（符合 AGENTS.md §2 借贷平衡、§2 期间不可随意修改）
- `/api/entries` — **仅**分录行级查询/修改/复核，逐步废弃 `/entries/vouchers/*`
- AI 草稿仍只写 draft 状态，正式入账走人工确认 + post（AGENTS.md §2.5、§7.2）

---

### 🟠 P1 — 标签：`entry-tags` vs `document-tags`

| 模块 | 端点 | 重叠能力 |
|------|------|----------|
| `/api/entry-tags` | 20 | CRUD、映射规则、向量同步、搜索 |
| `/api/document-tags` | 17 | 几乎同构 |
| `/api/entries/{id}/tags` | 4 | 分录内嵌标签 |

**目标**: 统一 Tag 服务，按 `object_type`（entry / document / voucher）区分，对外一套 REST。

---

### 🟠 P1 — 「Review」语义分散

| 位置 | 业务含义 |
|------|----------|
| `/api/entries/.../review` | 分录复核 |
| `/api/vouchers/.../post` | 凭证入账 |
| `/api/audit/review-requests` | 审计协作复核 |
| `/api/risks/{id}/review` | 风险复核 |
| `/api/audit-tests/findings/{id}/review` | 审计发现复核 |

**目标**: 文档与 OpenAPI tag 加域前缀；不合并 API，但统一命名规范（如 `accounting-review` vs `audit-review`）。

---

### 🟡 P2 — Dashboard / Report / LLM 分散

| 类型 | 端点示例 |
|------|----------|
| Dashboard | `/api/dashboard/summary`, `/api/audit/dashboard/*`, `/api/parser-engine/quality-dashboard` |
| Report | `/api/import-jobs/{id}/report`, `/api/audit-tests/{id}/report`, `/api/reports/*` |
| LLM | `/api/config/parser-engine/llm-*`, `/api/parser-engine/multi-llm-compare`, `/api/llm-resolution`, `/api/agent/*` |

**目标**: 配置归 config；运行时归 parser-engine/agent；业务解析归 llm-resolution；不在新功能中新增第四套入口。

---

## 四、收敛原则

### 4.1 必须遵守 AGENTS.md 的 API 设计约束

| AGENTS.md 章节 | 对 API 收敛的要求 |
|----------------|-------------------|
| §1.2 记账主线 | 路径命名体现 Project → Ledger → Voucher → Entry → Period → Report 层级 |
| §1.3 审计主线 | 审计 API 必须绑定 `ledger_id`；Review 与记账 review/post 语义分离 |
| §2 财务规则 | 过账/结账/损益结转 API 须带审计日志；closed 期间修改须权限校验 |
| §5.5 金额精度 | 金额相关 API 禁止 float；与 `Money`/`Decimal` 体系一致 |
| §8 任务治理 | 每个收敛 PR 须声明 Domain、In/Out Scope、L1–L6 目标层级 |
| §8 执行顺序 | 先收敛阻塞与主数据边界 API，再动 AI/向量增强类端点 |
| §9 安全 | 配置类 API（`/api/config`）须鉴权；敏感字段脱敏 |

### 4.2 结构性收敛原则

1. **每个业务能力只有一个主入口**；旧入口标记 `deprecated`，保留 ≥1 个版本周期。
2. **prefix 与 Router 文件 1:1**；禁止 3 个文件共挂 `/api/import-jobs`。
3. **凭证以 Voucher 为聚合根**；Entry 为子资源，不另立平行「凭证查询」树（见 §1.2）。
4. **导入/解析三件套**: `import-jobs`（任务）→ `parser-engine`（解析）→ `parser-voucher`（草稿确认）；AI 输出仅为草稿（§2.5）。
5. **审计与记账 API 结构对称**（§3）：同类操作（列表/详情/状态变更）命名模式一致。
6. **新 API 必须先查本文档 + AGENTS.md §8**，确认 Domain 归属与不重复后再加路由。

---

## 五、分阶段执行任务

| 阶段 | 任务 | 优先级 | 验收 |
|------|------|--------|------|
| **Phase 0** | 本文档评审 + 登记 `requirements-domain-index` | P0 | 团队确认主路径表 |
| **Phase 1** | 拆分 `import-jobs` 三 Router 为子前缀或合并文件 | P0 | OpenAPI 分组清晰；测试不变 |
| **Phase 2** | 前端与测试迁移到 `/api/vouchers`；废弃 `/entries/vouchers/*` | P0 | 无前端调用旧路径 |
| **Phase 3** | 标记 `/api/unified-import`、`/api/parse` deprecated | P1 | 响应头或文档注明 |
| **Phase 4** | Tag 服务统一设计 spec | P1 | 新 spec 三件套 |
| **Phase 5** | 印章 `/api/v1` → `/api/seals` | P2 | 旧路径兼容 redirect |
| **Phase 6** | 更新 `module-refactoring-plan` 中「API 不变」表述 | P2 | 文档与代码一致 |

---

## 六、与现有文档关系

| 文档 | 关系 |
|------|------|
| **`AGENTS.md`** | **最高约束**：财务规则、术语、代码规范、任务治理；本文档不得与之冲突 |
| `requirements-boundary-governance-plan.md` | 上级治理框架；本文档是其 **API 专项子计划** |
| `module-refactoring-plan.md` | 服务层重构须遵循本文档主路径，避免 refactor 时复制并行 API |
| `development-plan.md` P2 解析稳定性 | IMP-D/E 为主战场 |
| `current-risks-and-tasks.md` | 风险 2（解析→草稿）、风险 3（双解析）引用本文档 |
| `frontend-api-fix-plan.md` | 仅环境/连接；与本文档边界不重叠 |

**后续执行 spec 建议路径**: `.trae/specs/api-boundary-convergence/`（待创建，含 spec.md / tasks.md / checklist.md）

---

## 七、判定口径（给 AI / 开发使用）

新增或修改 API 前必须回答：

```text
0. 是否符合 AGENTS.md 财务规则与术语？（§1–§3、§8）
1. 该能力是否已有主路径？（见第三节表格）
2. 若已有，是否应扩展主路径而非新建 prefix？
3. Domain 归属 D01–D13 中的哪一个？
4. 是否影响 entries/vouchers 双轨？若影响，以 Voucher 为聚合根、Entry 为子资源。
5. AI 相关接口是否仅产出 draft/建议，不直接 post/close？（§2.5）
6. 是否需要 deprecated 清单条目？
7. 目标完成层级 L1–L6 是几？（§8）
```

---

## 八、文档维护

| 字段 | 值 |
|------|-----|
| 最后扫描日期 | 2026-07-04 |
| 扫描方法 | `routes_*.py` 静态 `@router.*` 计数 + 人工归类 |
| 下次复核触发条件 | 新增 routes 文件 / 合并 WIP / 发布前 |
| 维护者 | 项目治理（待指定） |
