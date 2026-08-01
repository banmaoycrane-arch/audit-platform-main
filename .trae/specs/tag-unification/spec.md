# Tag 服务统一设计 Spec（entry-tags / document-tags 收敛）

> **状态**: draft-待用户审阅
> **需求域**: D09 Tag/向量 + D12 工程治理
> **验收层级目标**: L3（设计定稿）→ L4（实施完成）→ L5（测试通过）；**不涉及 L6 人工签字**
> **依赖**: AGENTS.md §1.2/§3/§9、api-boundary-governance-plan.md §三/§四/§五 Phase 4、code-truth-status.md P2#12
> **上级治理**: [api-boundary-governance-plan.md](../../documents/api-boundary-governance-plan.md) §五 Phase 4
> **代码真值**: [code-truth-status.md](../../documents/code-truth-status.md) @ `1366f04`

---

## 0. 用户已确认的财务决策（本规格基础）

> 以下三项由会计专业用户于 2026-08-01 确认，技术方据此起草。涉及会计语义的判断尊重专业意见。

| 决策点 | 用户裁定 | 财务依据 |
|--------|----------|----------|
| **D1 标签口径是否合并** | **不合并，仅统一接口形态** | EntryTag 是「辅助核算维度」（影响明细账），DocumentTag 是「资料检索标签」（不参与核算）。财务语义不同构，强行合并会让核算维度丢失分类体系/主数据关联/权重，或让资料标签背上不适用字段。符合 AGENTS.md「审计与记账语义分离」。 |
| **D2 DocumentTag 账簿隔离** | **暂不补 ledger_id，spec 标记风险 + 后置** | P0 阻塞项「生产 Alembic 收口（stamp 0028→0034）」未完成，新增迁移会加剧收口负担。本轮预留参数位，等收口后执行迁移。 |
| **D3 entries 内嵌端点** | **废弃 /api/entries/{id}/tags，统一到 /api/entry-tags** | 符合治理计划「prefix 与 Router 文件 1:1」。旧路径用 307 重定向兼容（同 Phase 5 印章方案）。 |

---

## 1. Overview

### 1.1 Summary

收敛当前三套标签入口（`/api/entry-tags`、`/api/document-tags`、`/api/entries/{id}/tags`）的接口形态与隔离隐患，**不合并数据模型**。EntryTag（辅助核算维度）与 DocumentTag（资料检索标签）因财务语义不同构而保留两套表，本规格只做：

1. 废弃第三套内嵌端点 `/api/entries/{id}/tags`，307 重定向兼容；
2. 修复 DocumentTag 向量检索跨账簿串库隐患（预留 ledger_id 参数位，迁移后置）；
3. 统一 OpenAPI tag 命名规范与 deprecated 登记；
4. 文档真值同步（governance plan / code-truth-status / deprecated-api-list）。

### 1.2 Purpose

| 目标 | 说明 |
|------|------|
| 主路径唯一 | 分录标签操作只有 `/api/entry-tags` 一个入口，消除 entries 内嵌重复 |
| 账簿隔离不留漏网 | DocumentTag 向量检索预留 ledger_id 参数位，标记已知风险，为后置迁移铺路 |
| 财务语义不耦合 | 辅助核算维度与资料检索标签各自独立演进，不因接口统一而混淆核算口径 |
| 可审计 | deprecated 清单与治理文档登记真实状态，OpenAPI tag 域前缀清晰 |

### 1.3 财务语义对照（为什么不合并）

> 这是 D1 决策的依据，会计专业用户已确认。

| 维度 | EntryTag（分录标签） | DocumentTag（文档标签） |
|------|------|------|
| **财务语义** | 辅助核算维度（客户/供应商/项目/部门），影响明细账多维查询，是核算体系延伸 | 资料检索标签（业务/风险/关系/时间/金额/状态），仅用于原始文件分类与 AI 检索 |
| **是否参与核算** | 是（明细账过滤、辅助核算） | 否（服务层明示「不替代正式会计规则，不参与借贷平衡」） |
| **绑定对象** | 会计分录（强外键 CASCADE） | 原始文档（弱关联，无外键） |
| **账簿隔离** | ✅ 有 ledger_id，向量按账簿隔离 | ❌ 无 ledger_id（本规格标记风险，后置修复） |
| **分类体系** | TagCategory 树形维度（编码/父级/值类型/主数据来源） | 扁平 tag_type 字符串（6 类） |
| **主数据关联** | ✅ value_id 关联主数据档案 | ❌ 无 |
| **核算治理字段** | weight / reviewed_by_user / change_reason | confidence / source / operator / reason |

**通俗讲**：EntryTag 是「这笔分录挂在哪个客户/项目名下」——记账的一部分；DocumentTag 是「这张发票属于什么业务类型」——资料归档检索。两者服务的财务环节不同，合表会让「记账」和「归档」耦合。

### 1.4 Non-Goals（本规格明确不做）

- **不合并** EntryTag 与 DocumentTag 为单表（D1）
- **不新增** Alembic 迁移给 document_tags 加 ledger_id（D2，后置）
- **不改** EntryTag 的核算字段语义（weight/reviewed_by_user/分类体系保持）
- **不做** 前端页面大改（治理计划 Out of Scope）
- **不阻塞** 记账 v1.0 L6 / 审计 L6 签字
- **不删** 任何业务代码，旧路径保留 ≥1 版本周期兼容

---

## 2. 现状盘点（代码真值 @ `1366f04`）

### 2.1 三套入口

| 入口 | 文件 | 端点数 | 职责 |
|------|------|--------|------|
| `/api/entry-tags` | routes_entry_tags.py | 20 | 分录标签 CRUD + TagCategory 分类 + TagMappingRule 映射规则 + 向量同步/搜索 + 旧标签导入 |
| `/api/document-tags` | routes_document_tags.py | 17 | 文档标签 CRUD + 批量 + AI/规则/混合生成 + 统计 + 向量同步/搜索 + 历史 |
| `/api/entries/{id}/tags` | routes_entries.py L866-899 | 3 | 分录内嵌标签 GET/POST/DELETE（与 entry-tags 重叠） |

### 2.2 数据模型差异

- `EntryTag`（models.py L993）：强外键 `entry_id → accounting_entries`（CASCADE）、`ledger_id`、`category_id → tag_categories`、`value_id`、`weight`、`reviewed_by_user`、`vector_pending`
- `DocumentTag`（models.py L1926）：`document_id`（纯 Integer 无外键）、`document_type`、`tag`/`tag_type`、`vector_id`/`vector_stored`、**无 ledger_id**
- `TagCategory`（L967）：树形维度分类，绑定 ledger_id
- `TagHistory`（L1025）/ `DocumentTagHistory`（L1948）：两套独立历史表，字段结构不同

### 2.3 已识别隐患

1. **DocumentTag 向量跨账簿串库**：`document_tag_vector_service.py` collection 名固定 `document_tags`，payload 不含 ledger_id，检索无法按账簿过滤 → 违反 AGENTS.md 账簿隔离原则。EntryTag 已做隔离（`entry_tag_vector_service.py` + `vector_store_service.py` 按 ledger_id payload/filter）。
2. **第三套入口**：`/api/entries/{id}/tags` 与 `/api/entry-tags/tags` 功能重叠，违反治理计划 §四「prefix 与 Router 文件 1:1」。

---

## 3. What Changes

### 3.1 废弃 entries 内嵌端点（D3）

- `/api/entries/{entry_id}/tags` GET/POST、`/api/entries/{entry_id}/tags/{tag_id}` DELETE 标记 `deprecated=True`
- 旧路径返回 307 重定向到 `/api/entry-tags` 对应端点（保留 query），方案复用 Phase 5 印章 `compat_router` 模式
- OpenAPI `deprecated=True` + docstring `.. deprecated::` + tags 注明
- 前端 `client.ts` 迁移调用到 `/api/entry-tags`

### 3.2 DocumentTag 向量隔离预留（D2）

- `document_tag_vector_service.py` 的 `search_similar_tags` / `sync_pending_tags` 预留 `ledger_id: int | None` 参数位（向后兼容，默认 None）
- 向量 upsert 时 payload 增加 `ledger_id` 字段（若 DocumentTag 行已含 ledger 信息则写入；当前模型无该字段，payload 暂写 None）
- 检索时若传入 ledger_id 则按 payload filter 过滤（为后置迁移铺路）
- **不在本规格新增 Alembic 迁移**；在 spec/tasks 中登记后置任务：「等生产 stamp 收口 0028→0034 后，新增迁移给 document_tags 加 ledger_id + 向量重同步」

### 3.3 OpenAPI tag 命名规范统一

- `/api/entry-tags` 路由 tags 统一为 `entry-tags`（辅助核算维度）
- `/api/document-tags` 路由 tags 统一为 `document-tags`（资料检索标签）
- 废弃端点 tags 注明 `deprecated:entries-tags`
- 不改 URL 路径（避免前端动荡），仅规范 OpenAPI 元数据

### 3.4 文档真值同步

- `deprecated-api-list-v1.md`：登记 `/api/entries/{id}/tags` 三端点
- `api-boundary-governance-plan.md` §五 Phase 4：补「✅ spec 三件套完成」
- `code-truth-status.md`：P2#12 状态更新；DocumentTag 串库风险登记

---

## 4. Impact

### 4.1 受影响代码

| 文件 | 改动 |
|------|------|
| `backend/app/api/routes_entries.py` | L866-899 三端点 deprecated + 307 重定向 |
| `backend/app/services/doc_parsing/document_tag_vector_service.py` | 预留 ledger_id 参数位 + payload 字段 |
| `frontend/src/api/client.ts` | entries 内嵌 tags 调用迁移到 /api/entry-tags |
| `backend/tests/test_entry_tags_api.py` | 新增 redirect 兼容测试 |
| `backend/tests/test_document_tag_service.py` | 新增 ledger_id 参数位回归测试 |

### 4.2 受影响文档

- `deprecated-api-list-v1.md`、`api-boundary-governance-plan.md`、`code-truth-status.md`

### 4.3 不受影响

- EntryTag / DocumentTag / TagCategory / TagHistory 数据模型与表结构
- EntryTag 核算字段语义（weight/reviewed_by_user/分类体系）
- 现有向量数据（不重同步）

---

## 5. ADDED Requirements

### Requirement: entries 内嵌标签端点废弃

系统 SHALL 将 `/api/entries/{entry_id}/tags`（GET/POST）与 `/api/entries/{entry_id}/tags/{tag_id}`（DELETE）标记为 deprecated，并以 HTTP 307 重定向到 `/api/entry-tags` 对应端点，保留 query 参数。

#### Scenario: 旧路径 GET 重定向
- **WHEN** 调用 `GET /api/entries/123/tags`
- **THEN** 返回 307，Location 指向 `/api/entry-tags/tags?entry_id=123`

#### Scenario: 旧路径 POST 重定向
- **WHEN** 调用 `POST /api/entries/123/tags`（body 含标签数据）
- **THEN** 返回 307，Location 指向 `/api/entry-tags/tags`

#### Scenario: OpenAPI 标记 deprecated
- **WHEN** 读取 OpenAPI schema
- **THEN** 上述三端点 `deprecated: true`
- **AND** tags 含 `deprecated:entries-tags`

### Requirement: DocumentTag 向量检索预留账簿隔离参数

系统 SHALL 在 `document_tag_vector_service.search_similar_tags` 与 `sync_pending_tags` 预留 `ledger_id: int | None` 参数（默认 None，向后兼容），并在向量 payload 中写入 `ledger_id` 字段。

#### Scenario: 检索时不传 ledger_id（兼容现状）
- **WHEN** 调用 `search_similar_tags(query_text="差旅", ledger_id=None)`
- **THEN** 行为与现状一致（全局检索）

#### Scenario: 检索时传 ledger_id（为后置迁移铺路）
- **WHEN** 调用 `search_similar_tags(query_text="差旅", ledger_id=5)`
- **THEN** 按 payload `ledger_id=5` 过滤（当前因模型无该字段，过滤结果与 None 一致，不报错）

#### Scenario: 向量 upsert 写入 ledger_id 字段
- **WHEN** 同步 DocumentTag 到向量库
- **THEN** payload 含 `ledger_id` 键（值暂为 None，因模型无该字段）

### Requirement: OpenAPI tag 命名规范

系统 SHALL 确保 `/api/entry-tags` 路由 OpenAPI tags 为 `entry-tags`，`/api/document-tags` 路由 tags 为 `document-tags`，废弃端点额外注明 `deprecated:entries-tags`。

#### Scenario: 域前缀清晰
- **WHEN** 读取 OpenAPI schema
- **THEN** entry-tags 域端点 tags 仅含 `entry-tags`（与 `document-tags` 不混用）

---

## 6. 验收口径

| 项 | 验收标准 |
|----|----------|
| 旧路径兼容 | `/api/entries/{id}/tags` 三端点 307 重定向生效，4 个 redirect 测试通过 |
| 前端迁移 | `client.ts` 无对 `/api/entries/{id}/tags` 的调用 |
| 向量参数位 | `document_tag_vector_service` 预留 ledger_id 参数，向后兼容测试通过 |
| OpenAPI | deprecated 三端点标记 + tag 命名规范 |
| 文档真值 | deprecated-api-list / governance plan / code-truth-status 同步 |
| 回归 | pytest 全绿（当前基线 891/891）、前端 tsc 0 错误、vitest 77/77 |
| 财务语义 | EntryTag 核算字段不变、DocumentTag 不参与核算的定位不变 |

---

## 7. 后置任务（不在本规格执行，仅登记）

| 任务 | 触发条件 | 说明 |
|------|----------|------|
| DocumentTag 补 ledger_id 迁移 + 向量重同步 | 生产 Alembic stamp 收口 0028→0034 完成 | 新增迁移给 document_tags 加 ledger_id 列，向量 payload 回填，检索强制按账簿过滤 |
| 前端 DocumentTagsPage 账簿选择器 | 上项完成后 | UI 增加账簿维度筛选 |

---

## 8. 与现有文档关系

| 文档 | 关系 |
|------|------|
| AGENTS.md | 最高约束：§1.2 记账主线、§3 审计记账分离、§9 API 边界；本规格不与之冲突 |
| api-boundary-governance-plan.md | 上级：§三 P1 标签重叠、§五 Phase 4；本规格是其执行 spec |
| code-truth-status.md | 真值源：P2#12、L181 文档标签待合并；本规格完成后同步状态 |
| entry-tag-vector-sync spec | 前序：建立了 /api/entry-tags 主路径与向量同步；本规格在此基础上收敛内嵌端点 |
| Phase 5 印章 spec | 方案参考：307 compat_router 重定向模式 |

---

## 9. 待用户审阅确认项

> 本草稿已基于 2026-08-01 三项决策起草。请审阅以下设计细节是否符合预期，确认后定稿 tasks.md / checklist.md：

1. **废弃范围**：仅废弃 entries 内嵌 3 端点，不动 `/api/entry-tags` 与 `/api/document-tags` 现有路径——是否同意？
2. **向量参数位**：DocumentTag 向量服务预留 ledger_id 参数（默认 None，行为不变）——这种「先铺路不动数据」的方式是否认可？
3. **后置任务归属**：DocumentTag 补 ledger_id 迁移列为后置（等 Alembic 收口）——是否符合您的优先级排序？
4. **OpenAPI tag 命名**：仅规范元数据不改 URL——是否同意？
