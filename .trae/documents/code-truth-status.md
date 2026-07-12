# 代码真值状态（Code Truth Status）

> **文档类型**: 项目状态唯一真值来源  
> **更新日期**: 2026-07-12  
> **代码基准**: Git `main` @ `00cfaf4`（已 push `origin/main`）  
> **维护规则**: 任何规划文档、spec checklist、进度结论 **不得与此文冲突**；冲突时以本文 + 代码为准

---

## 一、如何使用本文

| 读者 | 用法 |
|------|------|
| 决策者（你） | 看 §三「主线完成度」与 §五「待办」决定 Sprint |
| AI / 开发 | 开工前读 §二「代码规模」+ §四「已知债务」；**架构分层**读 [ddd-layer-architecture-map.md](./ddd-layer-architecture-map.md)；**收敛章程**读 [development-convergence-charter.md](./development-convergence-charter.md)；新增 API 查 `api-boundary-governance-plan.md` |
| 旧文档 | `current-risks-and-tasks.md`、`development-plan.md` 等于 **派生摘要**；细节回链本文 |

**核验命令**（复现本文数据）：

```powershell
cd audit-platform-main\backend
.\.venv\Scripts\python.exe -m pytest tests --collect-only -q
.\.venv\Scripts\python.exe -m pytest tests -q
```

---

## 二、代码规模（2026-07-05 静态扫描）

| 指标 | 数值 | 路径 |
|------|------|------|
| 后端路由模块 | **53** | `backend/app/api/routes_*.py` |
| HTTP 端点 | **~366** | `@router.get/post/...` |
| 系统端点 | **2** | `/`, `/health` |
| **API 合计** | **~368** | `main.py` 注册 53 router |
| 后端测试用例 | **677** | `backend/tests/` |
| 前端页面组件 | **77+** | `frontend/src/pages/**/*.tsx` |
| 服务层文件 | **123** | `backend/app/services/**/*.py` |
| 活跃 spec 目录 | **60** | `.trae/specs/*/spec.md` |
| 规划文档 | **54+** | `.trae/documents/*.md` |

### 2.1 服务层领域结构（已落地）

```
backend/app/services/
├── accounting/      # 凭证、分录、期间、报表、EntryTag
├── audit/           # 审计任务、工作流、风险、底稿、序时簿
├── auth/            # 登录、权限
├── agent/           # Agent、LLM 客户端
├── basic_data/      # 科目、往来、合同、印章 OCR
├── doc_parsing/     # 导入、parser_engine、向量、文档标签
├── shared/          # 账簿、项目、生命周期、模块登记
└── （根目录残留）    # project_service.py 等，与 shared/ 部分重复 ⚠️
```

**重构状态**: 领域目录 **已提交**（`99a15db`）；根目录仍有少量重复服务文件，属技术债。

### 2.2 API 前缀分布（摘要）

| 域 | 端点约数 | 主前缀 |
|----|----------|--------|
| 导入/解析 | 59 | `import-jobs`, `parser-engine`, `parser-voucher`, `parse`, `unified-import` |
| 记账 | 91 | `vouchers`, `entries`, `accounting-periods`, `reports` |
| 审计 | 72 | `audit/*`, `workpapers`, `audit-tests` |
| 标签/AI | 70 | `entry-tags`, `document-tags`, `agent`, `llm-resolution`, `config` |
| 组织/基础 | 69 | `teams`, `projects`, `ledgers`, `coa`, `entities` |

**重叠结论**（详见 `api-boundary-governance-plan.md`）: 导入 5 链路、entries/vouchers 双轨、entry-tags/document-tags 同构 — **代码仍存在，尚未收敛**。

---

## 三、主线完成度（L1–L6，以代码为准）

完成层级定义见 `AGENTS.md` §8：L1 文档 → L2 模型 → L3 服务 → L4 API → L5 前端 → L6 测试+真实数据。

### 3.1 记账主线

| 能力 | L 级 | 代码证据 | 备注 |
|------|------|----------|------|
| Team/Project/Ledger/Auth | **L5** | `routes_team/project/ledger/auth` + 前端 onboarding | 可用 |
| 凭证 CRUD | **L5** | `routes_vouchers.py` + Create/Edit/Query 页 | 主路径 |
| 分录查询/复核 | **L5** | `routes_entries.py`（16 端点） | 与 vouchers **双轨** ⚠️ |
| 会计期间/损益结转/结账 | **L5** | `routes_accounting_periods.py` + `AccountingPeriodsPage` | 可用 |
| 三大报表 | **L5** | `routes_reports.py` + Balance/Income/Trial 页 | 可用 |
| Money 精度体系 | **L3–L4** | `backend/app/money/` + 测试 | 前端页面 **未全面迁移** |
| 记账闭环 L6 验收 | **L4** | `test_accounting_period_close_loop.py` 等 | **缺端到端人工验收记录**；凭证签章链已落地（见 §3.5） |

### 3.2 审计主线

| 能力 | L 级 | 代码证据 | 备注 |
|------|------|----------|------|
| 审计任务/分支/复核/批注/通知 | **L5** | `routes_audit_*` 9 模块 + Audit 前端页 | 可用 |
| 序时簿导入 | **L5** | `audit_day_book_service` + Step3 入口 | 可用 |
| 审计测试/发现/导出 | **L5** | `routes_audit_tests/export` + Step6 | 可用 |
| 工作底稿 | **L4–L5** | `routes_workpapers.py` + WorkpapersPage | 可用 |
| 业务循环/内控 | **L4** | `routes_business_cycles/internal_controls` + 测试 | API 有，业务深度有限 |
| 按循环审计 by_cycle | **L3–L4** | schema 支持 | 资料清单自动匹配 **未完成** |
| 审计闭环 L6 验收 | **L4** | 多份 workflow 测试 | **缺端到端人工验收记录** |

### 3.3 导入 / 解析主线

> **Spec 总纲**（2026-07-05 重构）：[parser-dual-scenario-strategy.md](./parser-dual-scenario-strategy.md) → `document-parsing-engine`（场景 A/B、TOP3、修正回流）

| 能力 | L 级 | 代码证据 | 备注 |
|------|------|----------|------|
| ImportJob 全流程 | **L5** | `routes_imports.py` 14 端点 | 主路径 |
| Parser Engine 双引擎 | **L4–L5** | `doc_parsing/parser_engine/*` + 管理/配置页 | 可用 |
| 解析→凭证草稿 | **L5** | `routes_parser_voucher.py` 3 端点 + `ParserVoucherPreview.tsx` | **已实现**（旧文档 B1–B7 已过时） |
| 解析修正回流 | **L3–L4** | `routes_parse_correction.py` + `ParseCorrectionRule` 模型 | WIP 已提交，待 96% 指标验收 |
| 解析质量指标 | **L3–L4** | `parse_quality_metric` + alembic 0022 | 看板部分可用 |
| 旧式 `/api/parse/{type}` | **L4** | `routes_document_parsing.py` | **建议 deprecated** |
| 统一导入 `/api/unified-import` | **L4** | 3 端点 | **建议 deprecated** |
| 解析稳定性 96% | **未验收** | — | development-plan P2 目标 **未达标** |

### 3.5 增量：结构化 Staging + 维度治理 + 向量隔离 + 导入门禁 + 凭证签章（2026-07-07~08）

> 本节为 `99a15db` 之后的代码增量，**尚未经 L6 人工签字**；实现与 [development-convergence-charter.md](./development-convergence-charter.md) 方向一致。

| 能力 | L 级 | 代码证据 | 备注 |
|------|------|----------|------|
| **Staging 流水线** | **L4–L5** | `0023_structured_import_staging` + `structured_import_service.py` | preview → staging → confirm；`StagingAccountingEntry` |
| **Step4 维度/凭证分两阶段** | **L5** | `Step4DimensionReviewPanel.tsx` + `reviewPhase` | 大批量（≥500 凭证）引导至维度中心 |
| **维度中心（单页治理）** | **L4–L5** | `LedgerDimensionsPage` + `components/dimensions/*` | 分类 / 解析映射 / 主数据 / 待处理队列 |
| **维度主数据 ↔ Staging 同步** | **L4** | `dimension_sync_service.py` | `sync_to_master`、待处理队列 `build_dimension_pending_queue` |
| **账簿级解析映射覆盖** | **L4** | `account_tag_config.py` + `routes_config.py` `/ledgers/{id}/account-tag-rules` | Phase 4；需重启后端注册路由 |
| **Staging 批量 LLM 补标** | **L3–L4** | `staging_llm_tag_resolution_service.py` | 待处理队列一键触发 |
| **维度就绪门禁** | **L4** | `dimension_readiness_service.py` | Step2 序时簿导入前须「确认规则已审阅」 |
| **向量 ledger 隔离** | **L4** | `entry_tag_vector_service.py` + `vector_store_service.py` | Qdrant payload/filter 按 `ledger_id`；历史向量需重同步 |
| **凭证签章链** | **L4** | `0024_voucher_signature_chain` + `voucher_signature_service.py` | 制单人（解析）→ 复核人（Step4 verified）→ 审核人（Step5 confirm） |
| **Working Ledger** | **L4** | `working_ledger_service.py` + `ledgers.is_working` | 审计 B1 模式隔离导入 |

**凭证签章语义（记账 L6 必备）**：

| 角色 | 字段 | 来源 |
|------|------|------|
| 制单人 | `source_preparer_name` | 序时簿列「制单人/经办人」解析 |
| 复核人 | `cross_reviewed_by_user_id` | 当前登录用户在 Step4 标记凭证 `verified` 时记名 |
| 审核人 | `approved_by_user_id` | 当前登录用户在 Step5 `confirm` 确认入账时记名 |

**待补**：签章信息在 Step4 凭证抽屉/UI 全面展示；`l6-acceptance-checklist.md` 路径 A 增加维度审阅与签章核对步骤。

### 3.4 增量功能（非阻塞主线）

| 能力 | L 级 | 代码证据 | 建议优先级 |
|------|------|----------|------------|
| 印章识别 | **L4** | `routes_seals.py` + basic_data/seal_* + 测试 | P2，不压过 P2/P3 主线 |
| 文档标签 | **L4–L5** | `routes_document_tags.py` + DocumentTagsPage | 与 entry-tags 重叠，待合并 |
| Agent / LLM | **L4** | `routes_agent`, `llm-resolution` | 增强项 |
| 采购三单匹配 | **L2** | `routes_purchase_match` + 占位页 | 不做生产承诺 |
| D11 扩展模块 | **L2** | PlaceholderModulePage 等 | Backlog |

---

## 四、测试与工程状态

| 项 | 状态 | 说明 |
|----|------|------|
| 测试收集 | **677** | `pytest tests --collect-only` |
| 全量通过 | **677 passed, 0 failed** | 2026-07-06 S1-5 全量跑绿；~290s |
| 阶段1修复摘要 | 见下 | isolated SQLite fixture、pl_transferred 结账前置、规则引擎测试隔离、合同 party commit、LLM import 路径 |
| mypy | **~351 错** | `TECH_DEBT.md` TD-001；strict 已关闭 |
| 覆盖率 | **~39%** | `TECH_DEBT.md` TD-003 |
| CI | 已配置 | `.github/workflows/ci.yml` |
| 本地密钥 | 未入库 | `backend/.env` gitignore，需本地配置 SECRET_KEY |

---

## 五、当前待办（按 AGENTS.md §8 执行顺序）

### P0 — 阻塞发布

1. ~~**全量 pytest 跑绿**~~ ⚠️ 2026-07-06 曾 677/677；**2026-07-09 实测有失败项**，发布前须再跑全绿（见 [bookkeeping-v1-decision-record.md §7](../backend/docs/bookkeeping-v1-decision-record.md)）
2. **记账 v1.0 L6 人工验收**（路径 A 签字；**先验收再修** — 见 [bookkeeping-v1-decision-record.md](../backend/docs/bookkeeping-v1-decision-record.md)）
3. **审计 L6 路径 B**（与记账 v1.0 独立，可并行）
4. **API 收敛 Phase 2**：统一 vouchers 主路径 — **L6 签字后**（章程冻结）
5. **回写本文 §3.5**：staging/维度增量 commit 基准与测试数

### P1 — 主线质量

4. **解析 P2 验收**：修正回流 + 96% 稳定性指标（非新功能）
5. **Money 前端迁移**（TECH_DEBT TD-002）
6. **清理服务层根目录重复文件**（seal_*、project_service 等）

### P2 — 治理与文档

7. 执行 `api-boundary-governance-plan.md` Phase 1–3
8. 合并 entry-tags / document-tags 设计 spec
9. 更新各 spec checklist：**不得写与本文矛盾的「已完成」**

### 明确不做（当前 Sprint）

- 多准则内核、Audit OS 远期架构
- 新增第 6 条导入/解析 API 链路
- D11 采购/进销存生产化

---

## 六、与旧文档的对照（过时内容标记）

| 旧文档/结论 | 代码真值 |
|-------------|----------|
| `current-risks` 风险2：B1–B7 未开发 | ❌ 已有 `parser-voucher` + 预览页 |
| `module-refactoring-plan` 任务1「待执行」 | ❌ 已执行（99a15db），残留清理待做 |
| `next-execution-roadmap` checklist「88 passed」 | ❌ 现为 677 用例全绿（2026-07-06） |
| `development-plan` P1「待做 embedding 修复」 | ✅ 已迁至 `doc_parsing/embedding_service.py` |
| 多个 spec「L5 全部完成」 | ⚠️ 仅 API/页面存在，L6 未统一验收 |

---

## 七、文档层级（重塑后）

```text
AGENTS.md                         财务规则 + API 原则 + 任务顺序
code-truth-status.md（本文）       ★ 代码真值 / 完成度 / 待办
api-boundary-governance-plan.md   API 重叠与收敛细则
requirements-domain-index.md      需求域与 spec 归属
current-risks-and-tasks.md          派生：风险与任务摘要 → 链到本文
development-plan.md                 派生：阶段目标 → 链到本文 §三
.trae/specs/*/                      单一增量；checklist 不得违背本文
```

**更新触发条件**: 每次 `main` 合并 significant PR、全量 pytest 结果变化、或 L6 验收完成时，更新本文日期与 §三–§五。
