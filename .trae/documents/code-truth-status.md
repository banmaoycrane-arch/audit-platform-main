# 代码真值状态（Code Truth Status）

> **文档类型**: 项目状态唯一真值来源
> **更新日期**: 2026-08-01（全量 pytest 882 绿、4 提交已 push 到 `origin/main`、Alembic head 0034、E1 事件工单后端+前端落地后修订）
> **代码基准**: Git `main` @ `4b42cc6`（已与 `origin/main` 对齐；含数据/运维负债修复、pytest 失败修复、安全修复、0028–0034 迁移、E1 事件工单）
> **人读总览**: [project-status-overview.md](./project-status-overview.md)（三层真值 · 下一步）  
> **维护规则**: 任何规划文档、spec checklist、进度结论 **不得与此文冲突**；冲突时以本文 + 代码为准

---

## 〇、生产库部署真值（2026-07-21 实测）

| 项 | 值 |
|----|-----|
| 服务器 | `47.122.117.76` · Docker 卷 `/data/finance_audit.db` |
| 入口 | HTTPS **`:8443`**（官网 nginx 占 80；8080 已关） |
| `prod_schema_audit.py` | **PASS**（模型表/列缺失 = 0） |
| DB 表数 | **122** |
| 模型表数（容器） | **120**（另有 DB-only `global_settings`） |
| `alembic_version`（生产） | **`0028_tax_city_egress_pool`** |
| 登录关键列 | `ledgers.is_working` / `project_id` **OK** |
| 税务出口池表 | 4 表已存在；`fix_legacy_db.py` 仍作兜底 |
| 业务数据 | 有用户/账簿；**分录≈0、审计任务=0** → 结构齐、L6 样例未跑 |

### 〇.1 Alembic 三层对齐（2026-08-01 实测）

| 层 | Alembic 尖端 | 说明 |
|----|--------------|------|
| Git `origin/main` 文件树 | **`0034_add_economic_event_workorder`** | 2026-08-01 push `4b42cc6` 后已与本地对齐；`0028`–`0034` 全部入库 |
| 本机工作区 / 测试环境 | **`0034_add_economic_event_workorder`** | 已通过 `alembic upgrade head` 对齐；工作区干净（`git status --porcelain` 空） |
| 生产 stamp（2026-07-21） | **`0028_tax_city_egress_pool`** | 与 Git 文件树脱节 6 个迁移（`0029`–`0034`）；**下次部署前必须收口到 0034** |

**上线纪律**：改模型必须同时更新 Alembic **与** `deploy/fix_legacy_db.py`，并用 `prod_deploy_full.sh` / `apply_prod_schema.sh`（见 [DEPLOY_SYNC.md](../../deploy/DEPLOY_SYNC.md)）。本次新增 `0030`–`0033` 涉及性能索引、数据完整性约束、脏数据清理；`0034` 新增经济事件工单 4 表，部署前需在 staging 复验。

### 〇.2 本机工作区相对 `main`（摘要）

详见 [project-status-overview.md §4](./project-status-overview.md)。要点：

- **工作区状态**: 2026-08-01 push 后 `git status --porcelain` 为空；此前登记的「未入库文档 / 未入库迁移 / 未提交代码」均已进入 `origin/main`（OS 总纲、实施排期、事件工单规格、`0028`–`0034` 迁移、模块登记增强、`Contract.deep_analysis` 等）
- **勿提交**: `backend/*test*.txt`、`mypy_output_full.txt` 等临时日志（已在 `.gitignore` 或待清理）

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

## 二、代码规模（2026-07-05 静态扫描；2026-07-21 路由数校正）

| 指标 | 数值 | 路径 |
|------|------|------|
| 后端路由模块 | **57**（原文档 53，已增 tax_egress 等） | `backend/app/api/routes_*.py` |
| HTTP 端点 | **~366+** | `@router.get/post/...` |
| 系统端点 | **2** | `/`, `/health` |
| **API 合计** | **~370+** | `main.py` 注册 router |
| 后端测试用例 | **882** | `backend/tests/` |
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
└── tax/             # 税务出口池
```

**重构状态**: 领域目录 **已提交**（`99a15db`）；根目录残留已于 `4f30bf1` 清理完毕（删除 `project_service.py`/`seal_detection_service.py`/`seal_extraction_service.py`/`ledger_management_service.py`/`platform_permission_service.py`/`summary_template_service.py` 6 个重复文件）；全量 grep 确认无旧路径导入残留。

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
| Agent / LLM | **L4** | `routes_agent`, `llm-resolution`；前端标「实验功能」 | 增强项，非主路径 |
| 税务城市出口池 | **L4** | `routes_tax_egress` + `0028_tax_city_egress_pool`；**未接真实税局** | 可选增值；主线仍为文件导入记账 |
| 经济事件工单 | **L5**（E1 后端+前端落地） | `routes_economic_events.py` + `economic_event_service.py` + `0034` 迁移 + `EconomicEventsPage`/`EconomicEventDetailPage`；10/10 后端测试通过 | E1 事件壳完成（创建/列表/详情/挂分录/挂证据/状态推进/时间轴）；E2 导入聚类、E3 Agent、E4 向量待开工；spec 见 [economic-event-workorder](../specs/economic-event-workorder/spec.md) |
| 采购三单匹配 | **L2** | `routes_purchase_match` + 占位页 | 不做生产承诺 |
| D11 扩展模块 | **L2** | PlaceholderModulePage 等 | Backlog |

---

## 四、测试与工程状态

| 项 | 状态 | 说明 |
|----|------|------|
| 测试收集 | **882** | `pytest tests --collect-only` |
| 全量通过 | **882 passed, 0 failed** | 2026-08-01 实测；~450s |
| 阶段1修复摘要 | 见下 | 已修复：close_period 自动损益结转、counterparty/TagCategory 进程缓存污染兜底、entry_generation_api 认证 headers、A10/A11 冒烟流程 |
| mypy | **0 错** | 276 source files，Success: no issues found |
| 覆盖率 | **~39%** | `TECH_DEBT.md` TD-003；核心服务已补充 90 个测试 |
| CI | 已配置 | `.github/workflows/ci.yml` |
| 本地密钥 | 未入库 | `backend/.env` gitignore，需本地配置 SECRET_KEY |

---

## 五、当前待办（按 AGENTS.md §8 执行顺序）

### P0 — 阻塞发布

1. ~~**全量 pytest 跑绿**~~ ✅ 2026-08-01 实测 882/882 passed
2. ~~**提交 git 变更**~~ ✅ 2026-08-01 push `4b42cc6` 到 `origin/main`；4 提交（9579069/344eff7/4f30bf1/4b42cc6）已入库；工作区干净
3. **记账 v1.0 L6 人工验收**（路径 A 签字；**先验收再修** — 见 [bookkeeping-v1-decision-record.md](../backend/docs/bookkeeping-v1-decision-record.md)）— **需会计专业用户签字，技术方不可代签**
4. **审计 L6 路径 B**（与记账 v1.0 独立，可并行）— **需会计专业用户签字，技术方不可代签**
5. **API 收敛 Phase 2**：统一 vouchers 主路径 — **L6 签字后**（章程冻结，见 [api-boundary-governance-plan.md](./api-boundary-governance-plan.md) §五）
6. **生产 Alembic 收口**：部署前将 stamp 从 0028 升级到 0034，并在 staging 复验 — **需运维操作**

### P1 — 主线质量

7. **解析 P2 验收**：修正回流 + 96% 稳定性指标（非新功能）
8. ~~**Money 前端迁移**~~ ✅ 已完成（见 TECH_DEBT TD-002）
9. ~~**清理服务层根目录重复文件**~~ ✅ 已完成（`4f30bf1` 删除 6 个根目录重复文件；grep 确认无旧路径导入残留）
10. **API 边界治理 Phase 1–3**：导入链路收敛、entry-tags/document-tags 合并（~~Phase 1~~ ✅ 2026-08-01 完成：`import-jobs` 三 Router 链式挂载，prefix 唯一定义；882/882 测试不变；~~Phase 3~~ ✅ 2026-08-01 完成：`/api/unified-import`、`/api/parse` 已四重注明 deprecated + 响应头中间件 `Deprecation: true` + `Sunset` + `Link`，5 个新测试，887/887 通过；Phase 2 受 L6 阻塞）

### P2 — 治理与文档

11. 更新各 spec checklist：**不得写与本文矛盾的「已完成」**
12. 合并 entry-tags / document-tags 设计 spec
13. ~~经济事件工单（D14）E1 事件壳~~ ✅ 后端+前端落地（2026-08-01）；E2 导入聚类 / E3 Agent / E4 向量待开工

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
| `next-execution-roadmap` checklist「88 passed」 | ❌ 现为 **882** 用例（2026-08-01 全绿） |
| `development-plan` P1「待做 embedding 修复」 | ✅ 已迁至 `doc_parsing/embedding_service.py` |
| 多个 spec「L5 全部完成」 | ⚠️ 仅 API/页面存在，L6 未统一验收 |
| 「生产无 alembic_version / 仅 116 表」 | ❌ **已过时**：2026-07-21 为 122 表 + 生产 stamp **`0028`** |
| 「Git head 迁移仍是 0028/0029」 | ❌ **已过时**：2026-08-01 push `4b42cc6` 后 `origin/main` 迁移尖端已是 **`0034`**；本机与远程对齐 |
| 「事件工单 / OS 排期尚未进 origin/main」 | ❌ **已过时**：2026-08-01 push `4b42cc6` 后 E1 后端+前端+spec+迁移均已入库 |
| pytest 全量仍有 1 失败 | ❌ 2026-08-01 实测 **882/882 passed** |

---

## 七、文档层级（重塑后）

```text
AGENTS.md                         财务规则 + API 原则 + 任务顺序
project-status-overview.md          ★ 人读总览（三层真值 / 下一步）
code-truth-status.md（本文）       ★ 代码真值 / 完成度 / 待办
implementation-plan-and-schedule.md 实施排期（知识储备分离）
ai-native-finance-os-definition.md  OS 总纲
api-boundary-governance-plan.md   API 重叠与收敛细则
requirements-domain-index.md      需求域与 spec 归属
current-risks-and-tasks.md          派生：风险与任务摘要 → 链到本文
development-plan.md                 派生：阶段目标 → 链到本文 §三
.trae/specs/*/                      单一增量；checklist 不得违背本文
```

**更新触发条件**: 每次 `main` 合并 significant PR、全量 pytest 结果变化、生产复测、或 L6 验收完成时，更新本文日期与 §〇–§五；并同步 [project-status-overview.md](./project-status-overview.md)。
