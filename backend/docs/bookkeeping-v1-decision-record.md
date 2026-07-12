# 记账模块 v1.0 — 决策记录（发布范围 · 先验收再修）

> **文档性质**：已决议的产品/发布范围决策记录（**非新功能开发清单**）  
> **状态**：已确认 — **当前阶段以 L6 人工验收为主，验收通过后再按缺陷清单修**  
> **决策日期**：2026-07  
> **关联文档**：
> - 代码真值与 L 级：[code-truth-status.md](../.trae/documents/code-truth-status.md)
> - L6 验收路径（路径 A）：[l6-acceptance-checklist.md](../.trae/documents/l6-acceptance-checklist.md)
> - 收敛章程（API 冻结至 L6）：[development-convergence-charter.md](../.trae/documents/development-convergence-charter.md)
> - Tag / 分录底线：[tag-vs-account-hierarchy.md](./tag-vs-account-hierarchy.md) §1.1–§1.2
> - 固定资产 v1.0（同级，**不在本版范围**）：[fixed-asset-v1-decision-record.md](./fixed-asset-v1-decision-record.md)

**本文档用途**：固定 **记账 v1.0 发布边界** 与 **「先验收再修」** 工作顺序，作为发布门禁与后续修缺陷的唯一决策起点。  
**与固定资产文档同级**：固定资产 v1.0 = 待开发起点；记账 v1.0 = **功能已在 L5，缺 L6 签字与验收驱动修复**。

---

## 1. 核心原则：先验收再修

| 原则 | 说明 |
|------|------|
| **不先扩功能** | v1.0 发布前 **禁止** 新增 D11 占位模块、固定资产、API Phase 2 大重构、多准则内核 |
| **先走通 L6** | 按 [l6-acceptance-checklist.md §路径 A](../.trae/documents/l6-acceptance-checklist.md) 用 **真实或标准样例账套** 逐步操作并 **签字** |
| **缺陷从验收来** | 验收步骤中记录的失败点 → 写入 **§7 缺陷台账** → 按 P0/P1 修，修完 **回归同一步骤** |
| **自动化为辅** | `pytest` 全绿是 **发布前必要条件**，但不替代人工 L6；自动化红项在验收并行登记，**验收阻塞项优先修** |
| **章程冻结** | [development-convergence-charter.md](../.trae/documents/development-convergence-charter.md)：**L6 签字前不启动 API Phase 2** |

```text
┌─────────────────────────────────────────────────────────────┐
│  Phase 0  本文档定范围（当前）                               │
│  Phase 1  L6 路径 A 人工验收 + 逐步签字（优先）              │
│  Phase 2  按 §7 缺陷台账修 P0 → 回归 L6 失败步骤           │
│  Phase 3  pytest 全绿 + 更新 code-truth-status               │
│  Phase 4  记账 v1.0 发布签字（§9）                           │
│  Phase 5  v1.1（API 收敛、Money 前端、签章 UI 等）         │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 记账 v1.0 业务定义

**主线**（与 AGENTS.md 一致）：

```text
项目 → 账簿 → 分录 → 凭证 → 期间 → 报表
```

**v1.0 用户可完成的一条闭环**（= L6 路径 A）：

```text
登录 → 选账簿
  → 维度中心「确认规则已审阅」
  → Step1–2 序时簿结构化导入（Staging 预览）
  → Step4 维度复核 → 凭证复核（签章：复核人）
  → Step5 确认入账（签章：审核人）→ 过账
  → 会计期间：损益结转 → 结账（如适用）
  → 试算平衡表 / 资产负债表 / 利润表 核对
```

**前端入口**：记账模式 `/entry`、财务总账 `/ledger/workspace`、凭证五步 `/ledger/vouchers/step/*`、核算结构 `/ledger/dimensions`。

---

## 3. 与现有 Tag / 分录体系（v1.0 必须兼容）

记账 v1.0 **不新建** 平行核算体系；与 [tag-vs-account-hierarchy.md §1.1–§1.2](./tag-vs-account-hierarchy.md) 一致。

| 层 | v1.0 要求 |
|----|-----------|
| **分录** `accounting_entries` | 金额、借贷、科目唯一真值；导入 confirm/post 后入账 |
| **EntryTag** | 序时簿解析沉淀维度；Step4 维度复核；`ledger_id` 隔离 |
| **Staging** | preview → 复核 → confirm，大批量引导维度中心 |
| **维度门禁** | 序时簿导入前须「确认规则已审阅」（`LedgerSettings.tag_rules_reviewed_at`） |
| **凭证签章链** | 制单（序时簿列）→ 复核（Step4 verified）→ 审核（Step5 confirm） |
| **Register** | v1.0 不含固定资产卡片；合同/发票等 Register **不扩新能力** |

**1601/1604 等 Tag 解析**：沿用 `account_tag_resolution_service` + 维度中心解析映射；不在 v1.0 改 Tag 体系。

---

## 4. v1.0 纳入范围（Must Have）

### 4.1 功能（代码已在 L5，验收须逐条签字）

| # | 能力 | 入口 / 证据 | L6 步骤 |
|---|------|-------------|---------|
| F1 | 团队 / 项目 / 账簿 / 登录 | onboarding、账簿管理 | A1–A2 |
| F2 | 核算结构：科目 + 维度 | `/ledger/dimensions`（含 COA tab） | A4 |
| F3 | 解析映射 + **维度就绪门禁** | parse-mapping tab、「确认规则已审阅」 | A4–A5 |
| F4 | 凭证 Step1–5（序时簿导入主路径） | `/ledger/vouchers/step/1`…`5` | A3–A8 |
| F5 | Staging 两阶段复核 | Step4 `reviewPhase=dimensions` | A7 |
| F6 | 确认入账 + 凭证过账 | Step5 confirm、`/api/vouchers/{id}/post` | A8–A9 |
| F7 | 会计期间 / 损益结转 / 结账 | `/accounting-periods` | A10 |
| F8 | 三大报表 | 试算 / 资产负债 / 利润 | A11 |
| F9 | 总账 / 明细账 | `/ledger/general-ledger`、`subsidiary-ledger` | A11 延伸 |
| F10 | 凭证 CRUD（手工补录） | create/edit/query | 样例账可选 |
| F11 | 内控缺陷清单（只读展示） | `/ledger/control-defects` | 勾稽差异可见即可 |

### 4.2 非功能（发布门禁）

| # | 项 | v1.0 标准 |
|---|-----|-----------|
| N1 | **L6 路径 A 人工签字** | [l6-acceptance-checklist.md](../.trae/documents/l6-acceptance-checklist.md) 路径 A **结论：通过** |
| N2 | **pytest 全绿** | `pytest tests -q` 0 failed（发布前最后一轮） |
| N3 | **账簿隔离** | 导入、Tag、向量按 `ledger_id`；跨账簿不串 |
| N4 | **签章可核对** | 至少 backend 字段正确；UI 全面展示 **v1.1** |
| N5 | **code-truth 回写** | 验收与测试完成后更新 [code-truth-status.md](../.trae/documents/code-truth-status.md) §三、§四 |

---

## 5. v1.0 明确排除（Must Not / v1.1+）

| 排除项 | 目标版本 | 说明 |
|--------|----------|------|
| API Phase 2（vouchers/entries 收敛） | v1.1 | 章程冻结至 L6 后 |
| import-jobs 三 router 拆分 | v1.1 | 治理项 |
| Money 前端全面 Decimal 迁移 | v1.1 | TD-002 |
| 签章 UI 全面展示 | v1.1 | 后端已有 |
| 现金流量表 **前端页** | v1.1 | 后端 API 可有 |
| 解析 96% 稳定性 **指标验收** | v1.1 | 质量项，不挡 v1.0 若样例账可走通 |
| **维度 manifest 预扫描**（结构化文件先识别 Tag 分类/取值） | v1.1 **P0** | 见 §10.1；v1.0 仍走解析后 registry |
| **维度主数据批量更新**（待处理队列批量确认、CSV 导入等） | v1.1 **P1** | 见 §10.2；依赖 manifest 落地后再做 |
| 固定资产模块 | 见 FA 决策文档 | 独立 v1.0 |
| D11 占位（银行日记账、税务、进销存生产化） | backlog | |
| 多准则内核 / Audit OS 远期架构 | 不做 | |
| 新增第 6 条导入 API 链路 | 不做 | |
| 物理 DDD 四层分包 | P2 backlog | |

---

## 6. L6 验收执行说明（Phase 1 操作手册）

**执行人**：__________ **计划日期**：__________

### 6.1 环境准备

| 项 | 要求 |
|----|------|
| 前端 | `http://127.0.0.1:5173` |
| 后端 | `http://127.0.0.1:8000`，**修改代码后须重启** |
| 样例 | 标准会计案例 CSV/Excel 序时簿（含制单人列）；或企业脱敏样例 |
| 账簿 | 新建或专用验收账簿，记录 `ledger_id=____` |

### 6.2 逐步验收（与路径 A 对齐）

| 步骤 | 操作 | 通过 □ | 失败现象 / request_id | 缺陷 ID |
|------|------|--------|------------------------|---------|
| A1 | 登录 | | | |
| A2 | 选择账簿 | | | |
| A3 | Step1 选「结构化 · 序时簿」 | | | |
| A4 | 维度中心 → 确认规则已审阅 | | | |
| A5 | Step2 上传（未审阅应拦截） | | | |
| A6 | 解析成功，staging 有数据 | | | |
| A7 | Step4 维度复核 → 凭证复核 | | | |
| A8 | Step5 确认入账 | | | |
| A9 | 凭证过账 | | | |
| A10 | 损益结转（如适用） | | | |
| A11 | 试算 / 资产负债 / 利润核对 | | | |

**签字**：__________ **结论**：□ 通过 □ 不通过（不通过则 **不得** 宣称 v1.0 发布）

### 6.3 验收通过附加核对（建议）

- [ ] 凭证签章：制单人 / 复核人 / 审核人字段与操作人一致（DB 或 API 可查）
- [ ] 三表与试算勾稽：资产 = 负债 + 权益（样例账口径）
- [ ] 维度门禁：未 A4 时 A5 被拦截
- [ ] 过账后正式分录可查询，staging 与正式账分离清晰

---

## 7. 缺陷台账（验收驱动 · Phase 2 填写）

> **规则**：L6 每一步失败或 pytest 红项，登记一行；**P0 = 挡路径 A**，**P1 = 不挡主路径但影响质量**。

| ID | 来源 | 描述 | 优先级 | 状态 | 修复 PR / 备注 |
|----|------|------|--------|------|----------------|
| D-001 | pytest | 序时簿/Staging 相关测试失败（`test_audit_day_book_import` 等） | P0 | 待验收后修 | 门禁与 fixture 对齐 |
| D-002 | pytest | `test_staging_llm_resolution` 收集错误（缺 `requests`） | P1 | 待修 | |
| D-003 | pytest | `test_entry_line_number` 失败 | P1 | 待修 | |
| D-004 | 用户反馈 | 维度「确认规则已审阅」500 | P0 | 已修待回归 | `dimension_readiness_service` + 账簿权限校验 |
| D-005 | 文档 | code-truth 测试数与实测不一致 | P1 | 待 L6 后回写 | |
| D-006 | L6-A__ | （验收时填写） | | 待填 | |
| … | | | | | |

**Phase 2 顺序**：先修 **挡 A4–A9 的 P0** → 回归对应 L6 步骤 → 再修 P1 → 全量 pytest → 重跑 L6 全路径。

---

## 8. 自动化测试范围（v1.0 发布前须全绿）

记账相关 **核心套件**（修缺陷时优先跑）：

| 文件 | 覆盖 |
|------|------|
| `test_dimension_readiness.py` / `test_dimension_readiness_api.py` | 维度门禁 |
| `test_audit_day_book_import.py` / `test_audit_day_book_api.py` | 序时簿 Staging |
| `test_vouchers_crud.py` / `test_voucher_post_api.py` | 凭证 |
| `test_voucher_signature_chain.py` | 签章链 |
| `test_accounting_period_close_loop.py` | 期间闭环 |
| `test_reports_api.py` / `test_financial_statements_service.py` | 三表 |

**命令**：

```powershell
cd audit-platform-main\backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

---

## 9. 发布签字清单（Phase 4）

以下 **全部勾选** 后，可对外称 **记账 v1.0 已发布**：

- [ ] L6 路径 A **结论：通过**（§6.2 签字）
- [ ] §7 缺陷台账 **P0 已全部关闭** 或豁免说明经确认
- [ ] `pytest tests -q` **0 failed**
- [ ] [code-truth-status.md](../.trae/documents/code-truth-status.md) 已更新（L6 记录、测试数、日期）
- [ ] v1.0 **排除项** 未偷偷合入（API Phase 2、FA、D11 生产化）
- [ ] 样例账套或验收账簿 ID 已归档备查

**发布签字**：__________ **日期**：__________

---

## 10. v1.1 预告（L6 通过后再排期）

**维度增强线排期（已确认）**：**manifest 先 → 批量主数据后**。与 Tag/分录底线（§3）兼容：manifest 只 seed 分类与主数据草稿，金额仍只在分录；批量操作只改主数据/display_name，不批量改已入账分录 Tag。

| 能力 | 说明 | 优先级 |
|------|------|--------|
| **§10.1 维度 manifest 预扫描** | 结构化文件上传后先产出「本批维度清单」 | **v1.1 P0** |
| **§10.2 维度主数据批量更新** | 待处理队列批量确认、往来/银行 CSV、共享 Tag 映射 | **v1.1 P1**（依赖 §10.1） |
| API 收敛 | vouchers 主路径，entries 仅分录行 | v1.1 |
| Money 前端 | TD-002 Decimal | v1.1 |
| 签章 UI | Step4 抽屉全面展示 | v1.1 |
| 现金流量表前端 | 接现有 reports API | v1.1 |
| 解析 96% | P2 指标与修正回流 | v1.1 |

### 10.1 维度 manifest 预扫描（v1.1 P0 · 先做）

**问题**：v1.0 在 **全量解析 → staging** 之后才汇总 `dimension-registry` / 待处理队列；有结构化文件时，表头与科目段已能推断 Tag 分类与取值，却未 **先识别、先保留**。

**目标流程**：

```text
结构化文件上传（Step2）
    ↓
① manifest 预扫描（新增，不写入分录）
   · 表头：客户 / 供应商 / 部门 / 项目 / 账号 …
   · 科目 + 解析映射：1122→customer、1002→bank_account …
   · 列内去重取值（计数 + 样例）
    ↓
② 写入账簿草稿（可人工改，带 job_id）
   · TagCategory：缺的自动建（提前于 `_ensure_tag_categories`）
   · 实体主数据：counterparties / bank_accounts 草稿或「待确认」
   · 共享 Tag：候选值池（部门、项目等），不强行全部进 counterparty 表
    ↓
③ 全量解析 → staging（Tag 与 manifest 对齐匹配）
    ↓
④ Step4 / 待处理队列（只处理例外，非从零发现）
```

**决策项**：

| ID | 内容 | 验收要点 |
|----|------|----------|
| D-020 | **manifest API + 存储**：`POST …/import-jobs/{id}/dimension-manifest`（或等价），绑定 `ledger_id` + `job_id` | 上传后、process 前或 process 后立即返回分类清单与取值统计 |
| D-021 | **Step2 / 维度中心 UI**：「本批维度清单」→「一键保留分类/草稿主数据」 | 用户未点保留时不阻塞 v1.0 式导入；保留后分类 tab 可见 |
| D-022 | **解析对齐**：staging `suggested_tags` 优先匹配 manifest 已保留的 category + value | 待处理队列条数相对 v1.0 明显下降（样例账可量化） |

**与现有代码关系**：

| 现有 | manifest 后 |
|------|-------------|
| `detect_structured_file_format`（仅格式） | 扩展或并列 **列语义 + 取值采样** |
| `_ensure_tag_categories`（解析中补分类） | 保留；manifest 可 **提前 seed**，解析时幂等 |
| `build_staging_dimension_registry`（解析后） | 改为 **manifest ∪ staging 差异** |

**不做（v1.1 manifest 边界）**：不根据 manifest 直接生成正式 `EntryTag`；不修改已入账分录。

### 10.2 维度主数据批量更新（v1.1 P1 · manifest 后做）

**问题**：初始建账常需 **整表对照一次**；v1.0 待处理队列与主数据页以 **逐条确认** 为主，大批量不现实。

**目标能力**（按实现顺序）：

| ID | 能力 | 现状 | v1.1 交付 |
|----|------|------|-----------|
| D-023 | **待处理队列批量确认 / 批量同步主数据** | 逐条「确认无误」；staging 侧有 `bulk_update_dimension_display_name` | 勾选多条 → 批量确认；`tag_value`→规范名批量写 counterparty/bank |
| D-024 | **往来单位 CSV 批量导入** | 单条 CRUD；已有 `batch-update-role` | UI + `POST …/counterparties/bulk-import`（或复用 manifest 导出格式） |
| D-025 | **银行账户批量导入 UI** | 后端已有 `POST /api/bank/accounts/bulk-import` | 维度值主数据页暴露入口，与 manifest 清单联动 |
| D-026 | **共享 Tag 批量规范名映射** | 部门/项目等随分录沉淀 | 原名→规范名映射表，批量应用到 staging + 候选池 |

**边界**：

- 批量改 **主数据 / staging display_name / 角色**，不批量改 **已过账分录** Tag（调整走凭证或专门变更流程）。
- D-023–D-026 **依赖 D-020–D-022**：manifest 先给出完整清单，批量操作才有明确对象集。

**建议实施顺序**：

```text
L6 通过 → D-020 manifest API
       → D-021 manifest UI + 一键保留
       → D-022 解析对齐 + 回归样例账
       → D-023 待处理队列批量确认
       → D-024 / D-025 往来·银行 CSV
       → D-026 共享 Tag 批量映射
```

---

## 11. 文档索引

| 文档 | 角色 |
|------|------|
| **本文档** | 记账 v1.0 发布范围 + 先验收再修 |
| [l6-acceptance-checklist.md](../.trae/documents/l6-acceptance-checklist.md) | 逐步验收表（路径 A/B） |
| [code-truth-status.md](../.trae/documents/code-truth-status.md) | 代码 L 级与待办真值 |
| [development-convergence-charter.md](../.trae/documents/development-convergence-charter.md) | API/品牌冻结 |
| [fixed-asset-v1-decision-record.md](./fixed-asset-v1-decision-record.md) | 固定资产（独立线，非 v1.0） |

---

*最后更新：2026-07 — 定稿「先验收再修」；v1.1 维度线确认 **manifest 先、批量主数据后**（§10.1–§10.2，D-020–D-026）；L6 签字与 §7 缺陷台账待执行。*
