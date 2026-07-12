# 开发收敛章程（Development Convergence Charter）

> **文档类型**: 治理章程 — 防发散、对齐 DDD / 品牌 / API  
> **更新日期**: 2026-07-06  
> **状态**: active — 与 [AGENTS.md](../../AGENTS.md)、[code-truth-status.md](./code-truth-status.md) 同级约束  
> **读者**: 你（决策者）、AI、后续维护者

---

## 一、你的预期 vs 现状（差距总表）

| 预期维度 | 目标状态 | 当前差距等级 | 一句话 |
|----------|----------|--------------|--------|
| **干净 DDD 分包** | 接口 / 应用 / 领域 / 基础设施物理可辨 | 🟠 **中** | 已有领域目录，但同文件混层、无 Repository |
| **单一解析品牌** | 对外一套名称，对内双场景可解释 | 🔴 **高** | 「统一解析引擎」指代 3 条不同链路 |
| **API 全收敛** | 每能力一个主入口 + deprecated 清单 | 🔴 **高** | ~368 端点，导入 5 链、凭证双轨 |
| **文档可维护** | 单一真值 + 派生摘要 | 🟠 **中** | code-truth 已立，旧 checklist 仍冲突 |
| **主线不发散** | 只扩 P0/P1 章程内项 | 🟠 **中** | D11 占位、印章/Agent 易抢带宽 |

**结论**：引擎**选路**已对齐双场景 Charter；差距主要在 **工程治理与对外一致性**，不是重做解析内核。

---

## 二、问题识别（按根因聚类）

### 问题簇 A — DDD 逻辑清晰、物理不干净

| # | 具体问题 | 代码/文档证据 | 维护风险 |
|---|----------|---------------|----------|
| A1 | **应用层与领域层同文件** | `audit_day_book_service.py` 同时编排落库 + 借贷平衡/跳号规则 | 改规则易破坏流程；难单测引擎 |
| A2 | **接口层渗业务** | 部分 `routes_*.py` 含分支组装、直接调多个引擎 | API 变更牵一发动全身 |
| A3 | **无基础设施抽象** | 领域服务直接 `Session`、`Path`、HTTP 调 LLM | 换 DB/存储/模型成本高 |
| A4 | **服务重复入口** | 根目录 `project_service.py`、`seal_*` 与子包并存 | 改一处漏一处 |
| A5 | **贫血模型** | `db/models.py` 无领域行为，规则散落 service | 规则重复、边界模糊 |

**不属于「错误」、属于阶段选择**：模块化单体 + 领域**目录**（`99a15db`）已是刻意权衡；**物理四层分包**需单列 Sprint，不可与 L6 验收混做。

---

### 问题簇 B — 「单一解析品牌」未建立

| # | 具体问题 | 表现 | 用户/开发者误解 |
|---|----------|------|-----------------|
| B1 | **品牌 umbrella 过大** | UI/API 统称「统一解析引擎」 | 以为序时簿也走 parser-engine 管理页 |
| B2 | **三条并行链路未命名** | A 自适应 / 登记 ingest / B Dispatcher | 调试 draft/9 类问题时找错模块 |
| B3 | **函数名暗示单引擎** | `parseSourceFileWithEngine`、`DocumentParserService` | 前端开发者假设单一后端 |
| B4 | **否决方案文档仍 OPEN** | `debug-parser-engine-unification.md` | 新需求仍追求「全 parser-engine」 |
| B5 | **旧引擎架构文档** | `engine-architecture.md` v1.0 单引擎叙事 | 与双场景 Charter 冲突（v1.1 已加指针） |

**收敛口径（对外单一品牌，对内双场景）**：

```text
品牌名（对外）：资料解析中心 Document Intelligence
  ├─ 结构化导入（场景 A）— adaptive-import-engine
  ├─ 原始资料解析（场景 B）— document-parsing-engine
  └─ 资料登记（场景 B 出口子路径）— register ingestion（非第三套引擎）
```

---

### 问题簇 C — API 未收敛（发散主因）

| # | 并行链路 | 前缀 | 治理决策 |
|---|----------|------|----------|
| C1 | IMP-A 主路径 | `/api/import-jobs` | **保留**（任务中枢） |
| C2 | IMP-B | `/api/unified-import` | **deprecated** → 只读兼容 |
| C3 | IMP-C | `/api/parse/{type}` | **deprecated** |
| C4 | IMP-D | `/api/parser-engine` | **保留**（B 运行时 + 调试） |
| C5 | IMP-E | `/api/parser-voucher` | **保留**（草稿确认） |
| C6 | 凭证双轨 | `/api/vouchers` vs `/api/entries` | **vouchers 主路径**，entries 仅分录行 |
| C7 | prefix 混挂 | 3 个 router 共 `/api/import-jobs` | **拆文件或拆 prefix** |
| C8 | 配置 vs 运行 | `/api/config/parser-engine` vs `/api/parser-engine` | 文档划界，禁止新第四入口 |

详见 [api-boundary-governance-plan.md](./api-boundary-governance-plan.md)。

---

### 问题簇 D — 文档多源、易发散

| # | 问题 | 后果 |
|---|------|------|
| D1 | 60 specs + 54 documents，部分 checklist 过时 | AI/人按旧文做重复或冲突需求 |
| D2 | 无「冻结/否决」清单集中展示 | 已否决的 unification 仍被引用 |
| D3 | L6 验收无签字记录 | 无法判断「算不算做完」 |
| D4 | 派生文档未强制回链 code-truth | README、development-plan 与代码漂移 |

**真值链（强制）**：

```text
代码 + code-truth-status.md
    → parser-dual-scenario-strategy.md（解析产品）
    → ddd-layer-architecture-map.md（分层对照）
    → 本文（收敛章程）
    → current-risks-and-tasks.md（Sprint 派生）
    → 各 spec（增量，不得扩域）
```

---

### 问题簇 E — 主线外的范围膨胀（防发散）

| 项 | 域 | 章程处置 |
|----|-----|----------|
| D11 扩展模块占位 | 采购三单、Placeholder | **冻结** — 不接主线 Sprint |
| 印章识别增强 | seal-recognition | **P2** — 仅服务场景 B Layer1，不单独扩 API |
| Agent 多角色编排 | agent | **增强项** — 不阻塞记账/审计 L6 |
| Money 前端全面迁移 | 工程 | **P1** — 与凭证主路径同步，不单开页面大战 |
| by_cycle 资料自动匹配 | 审计 | **Backlog** — 字段已有，不假装完成 |
| 物理 DDD 四层目录 | 架构 | **P2 重构** — 解析稳定 + API 收敛后再做 |

---

## 三、原定计划（不变的主线）

来自 [AGENTS.md](../../AGENTS.md) + [current-risks-and-tasks.md](./current-risks-and-tasks.md)：

```text
记账：项目 → 账簿 → 分录 → 凭证 → 期间 → 报表
审计：任务 → 业务循环 → 风险 → 证据/底稿 → 发现 → 报告
解析：场景 A 序时簿直接分录 + 场景 B 原始资料 → 台账/草稿（不自动 post）
```

**当前阶段官方优先级（不得自行调高）**：

| 优先级 | 内容 | 完成定义 |
|--------|------|----------|
| **P0** | pytest 全绿 + 记账/审计各 1 条 L6 人工路径 + API Phase 2 启动 | 签字 + CI 绿 |
| **P1** | 解析稳定性验收 + vouchers 主路径 + deprecated 标记 | OpenAPI 注释 + 前端无新调旧 API |
| **P2** | 文案/品牌统一 + 服务去重 + DDD 文件拆分（解析域试点） | ddd-map 可逐文件勾选 |
| **冻结** | D11 占位、新 import API、全 parser-engine 统一、大规模新 spec | PR 拒绝 |

---

## 四、收敛行动（可执行，按顺序）

### 阶段 1 — 止血（1–2 Sprint，不改财务规则）

| ID | 动作 | 产出 |
|----|------|------|
| S1-1 | 标记 **IMP-B、IMP-C** deprecated（OpenAPI + 路由 docstring） | deprecated 清单 v1 |
| S1-2 | 前端 **禁止新增** 对 `unified-import`、`/parse/` 的调用 | grep CI 或 review 规则 |
| S1-3 | Step2/Step3 **文案三分法**（结构化导入 / 原始资料解析 / 资料登记） | 前端 copy 表 |
| S1-4 | `debug-parser-engine-unification.md` 标 **superseded** | 链接到 dual-scenario |
| S1-5 | 全量 pytest 修到 0 failed | 更新 code-truth §四 |

### 阶段 2 — API 与品牌（2–3 Sprint）

| ID | 动作 | 产出 |
|----|------|------|
| S2-1 | 拆分 `/api/import-jobs` 三 router 或拆 prefix | api-boundary Phase 2 |
| S2-2 | `vouchers` 为凭证唯一聚合根；`entries/vouchers/*` deprecated | 前端迁移清单 |
| S2-3 | 对外文档统一 **资料解析中心** 品牌 + 子能力表 | README + 帮助文案 |
| S2-4 | `client.ts` 重命名：`parseImportJobFile` 等中性名 | 减少 Engine 暗示 |

### 阶段 3 — DDD 物理分包（解析域试点，3+ Sprint）

| ID | 动作 | 产出 |
|----|------|------|
| S3-1 | 新建 `application/import/`、`domain/parsing/`、`infrastructure/` **仅解析域** | 目录规范 v1 |
| S3-2 | 从 `audit_day_book_service` **抽出** `VoucherGroupingPolicy`、`BalanceCheck` 到 domain | 单测不依赖 DB |
| S3-3 | `routes_imports` 瘦身为纯接口 | 编排进 application |
| S3-4 | 记账域复制试点模式（仅 voucher 创建链） | 第二域模板 |

**禁止**：阶段 3 未完成前全仓库大迁移（避免同时动解析 + 审计 + API）。

---

## 五、新需求 / PR 准入检查（防发散）

每条 PR 或 spec 必须回答：

1. **Domain**：属于 D04/D05/D06/D12 哪一条？D11 一律拒绝进 Sprint。
2. **主路径**：是否新增第二套 API？若是 → 必须先改 api-boundary 计划。
3. **解析**：场景 A 还是 B？是否误用「统一引擎」一词？
4. **层级**：新代码落在哪一层？是否又塞进巨型 service？
5. **L 级**：目标 L3/L4/L5/L6？L6 是否需要人工验收记录？
6. **文档**：是否只改 code-truth 派生链上的文件？

---

## 六、文档齐全性清单（后期维护最低集）

| 文档 | 维护责任 | 更新触发 |
|------|----------|----------|
| [code-truth-status.md](./code-truth-status.md) | 每个 Sprint 末 | pytest 数、L 级、端点数 |
| [parser-dual-scenario-strategy.md](./parser-dual-scenario-strategy.md) | 解析产品变更 | 场景边界变化 |
| [ddd-layer-architecture-map.md](./ddd-layer-architecture-map.md) | 重构 PR | 文件迁移 |
| [api-boundary-governance-plan.md](./api-boundary-governance-plan.md) | API PR | 新/废路由 |
| [core-business-concepts-boundary.md](./core-business-concepts-boundary.md) | 需求评审 | 新概念 |
| 本文 | 章程修订 | 优先级调整 |
| 各 spec `spec.md` | 功能 PR | In/Out Scope 内 |

**不维护**：与真值冲突的 debug-*.md checklist 结论；应标 superseded 或归档。

---

## 七、是否符合预期 — 决策树（给你用）

```text
问：这个迭代算不算「对齐预期」？

1. 记账 + 审计 L6 是否各有一条签字路径？ ─否→ 未对齐，停扩功能
2. pytest 是否全绿？ ─否→ 未对齐，只修测试/债务
3. 是否新增第 6 条导入 API？ ─是→ 未对齐，违反章程
4. 对外是否仍只有一个解析品牌故事？ ─否→ 先做 S1-3/S2-3
5. 解析域文件能否在 ddd-map 找到唯一主层？ ─否→ 接受为 P2 技术债，记入 backlog

全部通过 → 可在 P2 做 DDD 物理分包与扩展域
```

---

## 阶段 1 执行状态（2026-07-06）

| ID | 任务 | 状态 |
|----|------|------|
| S1-1 | `unified-import`、`/api/parse` deprecated | ✅ 已完成 — 见 [deprecated-api-list-v1.md](./deprecated-api-list-v1.md) |
| S1-2 | 前端无 deprecated API 新调用 | ✅ 已核验（存量 0） |
| S1-3 | Step1/2/3 文案三分法 | ✅ 已完成 |
| S1-4 | `debug-parser-engine-unification` superseded | ✅ 已完成 |
| S1-5 | pytest 全绿 | ✅ 已完成 — 677 passed, 0 failed（2026-07-06）；见 code-truth §四 |
| S1-L6 | L6 人工路径签字 | 📋 模板 — [l6-acceptance-checklist.md](./l6-acceptance-checklist.md) |

**阶段 2 冻结**：在 S1-5 全绿 + L6 双路径签字前，不启动 API 拆分与 DDD 物理分包。

---

## 八、一句话章程

**主线只做记账闭环、审计闭环、双场景解析三条；对外一个「资料解析中心」品牌，对内 A/B/登记三子能力；API 只减不增直到 IMP-B/C 退役；文档以 code-truth 为根，spec 不得扩新域。**
