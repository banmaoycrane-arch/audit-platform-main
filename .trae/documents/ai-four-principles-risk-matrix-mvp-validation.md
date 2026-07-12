# 功能 × 四原则风险矩阵 + MVP 验证清单

> **文档类型**: 产品验证章程 — 对齐商业化四原则与当前 Sprint  
> **更新日期**: 2026-07-12  
> **对齐**: [sprint-iteration-control-2026-07-12.md](./sprint-iteration-control-2026-07-12.md) §二主线 / §三边界 / §四两周节奏  
> **代码基准**: `main` @ `6628d88`  
> **读者**: 决策者、产品、开发（埋点实施）

---

## 一、四原则操作定义（本 Sprint 口径）

| 原则 | 操作定义 | 通过线（MVP） | 失败信号 |
|------|----------|---------------|----------|
| **P1 AI税** | 引入 AI 后，用户完成任务的路径长度或耗时 **净减少** | 中位耗时 ≤ 非 AI 基线 × 0.8，或步骤数减少 ≥ 1 | 多一轮对话、多一页配置、仍全手改 |
| **P2 万能助手幻觉** | 场景足够窄，用户 10 秒内能说清「我要完成什么」 | 单屏单任务；入口嵌在任务流内 | 全局聊天、20+ 工具、多 Agent 编排 |
| **P3 隐性成本账** | 用户为 **ROI** 付费，不为 Token 付费 | 单次 AI 调用关联 ≥1 次「保存/入账/归档」 | 百轮对话 0 采纳；本地档用户被迫上云 |
| **P4 验证前置** | 先 Wizard of Oz / 埋点，再扩功能 | 两周内可读出采纳率、完成率 | 先开发后问「好不好用」 |

**商业化档位与 AI 策略**

| 档位 | 卖点 | AI 默认策略 | 计费锚点 |
|------|------|-------------|----------|
| 高隐私（低订阅 + 本地一次性） | 规则解析、本地证据、入账闭环 | **规则优先**，LLM 可选插件 | 账簿数 / 年 |
| 上云高档（高订阅） | 批量 SLA、协同、归档合规 | 场景 A 加速 + 可选增强 | 已入账凭证数 / 已归档证据数 |

---

## 二、功能 × 四原则风险矩阵

**图例**: 风险 — `高` / `中` / `低` / `安全`；Sprint — `P0主线` / `P1观察` / `冻结` / `不做`

| # | 功能 / 需求 | Sprint | P1 AI税 | P2 万能助手 | P3 隐性成本 | P4 验证缺失 | 综合 | 两周动作 |
|---|-------------|--------|---------|-------------|-------------|-------------|------|----------|
| F01 | **L6 记账路径**（导入→Step4→Step5→三大表） | P0主线 | 低 | 安全 | 低 | 中 | **安全** | 采完成率基线；不修非阻塞 |
| F02 | **场景 A TOP3**（序时簿/流水/发票 Excel） | P0主线 | 低 | 安全 | 低 | 中 | **安全** | 20 样本字段映射率 |
| F03 | **证据云空间**（收件箱/归档/ingest） | P0主线 | 安全 | 安全 | 安全 | 低 | **安全** | 归档完成率 |
| F04 | **内控工作台**（三源聚合待办） | P0主线 | 安全 | 低 | 安全 | 低 | **安全** | 待办点击→处理率 |
| F05 | **规则风险识别** | P0主线 | 安全 | 安全 | 安全 | 低 | **安全** | 维持；不 LLM 化 |
| F06 | **AI 凭证草稿**（Step3→Step4 staging） | P0主线 | 中 | 低 | 中 | **高** | **中** | **P0 埋点 + 采纳率** |
| F07 | **解析自动采纳**（置信度阈值） | P1观察 | 中 | 低 | 中 | **高** | **中** | 埋点「采纳后被改率」 |
| F08 | **Agent 对话控制台** `/agent` | 冻结 | **高** | **高** | **高** | **高** | **高** | WoO 规则后端；不扩工具 |
| F09 | **多 Agent 编排**（尽调/审批/草稿链） | 冻结 | 高 | **高** | 高 | **高** | **高** | 不做新步骤；仅日志 |
| F10 | **用对话替代 5/6 步向导** | 不做 | 高 | **高** | 高 | 高 | **高** | 章程明确不做 |
| F11 | **场景 B 全链路 LLM**（合同/扫描/融合） | P1观察 | 高 | 高 | **高** | **高** | **高** | TOP3 验收后再开 |
| F12 | **ParserEngine 多 LLM 并行** | P1观察 | 中 | 中 | **高** | 高 | **高** | 仅高档；要采纳证明 |
| F13 | **合规审查 SSE 流式** | 冻结 | 中 | 中 | 中 | 高 | **中** | 保留结果；弱化流式 |
| F14 | **解析引擎配置页**（路由/并行/阈值） | P1观察 | 中 | 中 | 中 | 中 | **中** | 配置变更记日志 |
| F15 | **向量业务循环识别** | P1观察 | 中 | 中 | 中 | 高 | **中** | 延后至 F06 达标后 |

### 矩阵结论（决策用）

```text
继续押注（P0）：F01–F05 + F06 的「采纳率验证」
两周只观察（P1）：F07、F14
本 Sprint 冻结扩面：F08、F09、F13
明确不做：F10
TOP3 后再议：F11、F12、F15
```

---

## 三、MVP 验证清单（埋点字段）

### 3.1 设计原则

- **事件名**：`snake_case`，前缀按域：`product_`（前端）、`ai_`（AI 输出）、`task_`（任务完成）
- **必带上下文**：`user_id`, `team_id`, `ledger_id`, `deployment_tier`（`local_privacy` | `cloud_premium`）
- **不写 PII**：消息正文不入库；只记 `message_length`、`intent`
- **存储**：Phase 0 写 `product_events` SQLite 表或现有 `execution_audit_log` 扩展；不阻塞 L6

### 3.2 核心 KPI 公式

| KPI | 公式 | MVP 通过线 |
|-----|------|------------|
| **AI 输出采纳率** | `fields_adopted_unchanged / fields_total`（凭证草稿） | ≥ **60%** |
| **AI 任务完成率** | `sessions_with_save_or_post / sessions_with_ai_output` | ≥ **40%** |
| **任务完成率（无 AI）** | `jobs_reached_step5_post / jobs_created` | ≥ **70%**（L6 基线） |
| **助手成功轮次比** | `sessions_task_completed / agent_rounds_total` | ≥ **0.25**（平均 ≤4 轮完成） |
| **路径建议点击率** | `suggested_path_clicked / suggest_system_path_success` | ≥ **50%** |
| **解析自动采纳后改率** | `auto_fields_later_edited / auto_fields_adopted` | ≤ **30%** |

### 3.3 事件字典（Phase 0 最小集）

#### E01 `ai_voucher_draft_shown`

用户看到 AI 生成的凭证草稿（Step4 / parser-voucher）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | uuid | 去重 |
| `job_id` | int | 导入任务 |
| `voucher_id` | int? | 草稿 ID |
| `source_file_id` | int? | 原始资料 |
| `fields_total` | int | 可编辑字段总数（科目/金额/摘要等） |
| `llm_used` | bool | 是否调用 LLM |
| `parser_route` | string | `rule` \| `llm` \| `auto-local` \| `auto-cloud` |
| `confidence_avg` | float? | 解析置信度均值 |

**触发**：`StagingVoucherReviewDrawer` 打开且 `draft_source=ai`

---

#### E02 `ai_voucher_draft_saved`

用户保存草稿（含编辑后保存）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `job_id` | int | |
| `voucher_id` | int | |
| `fields_adopted_unchanged` | int | 与 AI 初稿一致字段数 |
| `fields_edited` | int | 用户修改字段数 |
| `fields_rejected` | int | 清空/重写字段数 |
| `time_to_save_seconds` | int | 从 `draft_shown` 到保存 |
| `edit_distance_ratio` | float | `fields_edited / fields_total` |

**采纳率**：`fields_adopted_unchanged / fields_total`

---

#### E03 `task_bookkeeping_step_reached`

记账向导步骤到达（无 AI 完成率基线）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `job_id` | int | |
| `step` | string | `step1_select` … `step5_post` |
| `duration_from_prev_seconds` | int? | |

**完成率**：`count(step=step5_post) / count(step=step1_select)`

---

#### E04 `task_evidence_archived`

证据从收件箱归档成功。

| 字段 | 类型 | 说明 |
|------|------|------|
| `file_id` | int | |
| `archive_target` | string | `project` \| `period` \| `category` |
| `upload_channel` | string | `ui_drag` \| `ingest_api` \| `import` |

---

#### E05 `agent_assist_session`

一次 `/api/agent/assist` 往返（**F08 冻结期仍要记**）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | uuid | 前端生成，同会话多轮共享 |
| `round_index` | int | 第几轮 |
| `intent` | string | `general_help` 等 |
| `confidence` | float? | |
| `source` | string | `llm` \| `rules` |
| `tools_executed_success` | int | |
| `tools_executed_failed` | int | |
| `tool_names` | string[] | 不含参数 |
| `suggested_path` | string? | |
| `suggested_path_clicked` | bool | 前端补记 E06 |
| `llm_error` | string? | 截断 200 字符 |
| `task_completed` | bool | 本轮是否导致业务动作（查询结果已用=弱完成） |

**灾难信号**：`round_index > 5` 且 `task_completed=false`

---

#### E06 `agent_suggested_path_click`

用户点击助手推荐的路径。

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | uuid | |
| `path` | string | |
| `seconds_since_suggest` | int | |

---

#### E07 `parser_auto_adopt`

解析引擎自动采纳字段。

| 字段 | 类型 | 说明 |
|------|------|------|
| `parse_job_id` | string | |
| `field_name` | string | |
| `confidence` | float | |
| `engine_id` | string? | 并行引擎时 |

配对 **E08** `parser_field_later_edited`（用户后续改掉自动采纳字段）→ 算「自动采纳后改率」

---

#### E08 `workbench_todo_action`

工作台待办点击与处理。

| 字段 | 类型 | 说明 |
|------|------|------|
| `todo_id` | string | |
| `todo_source` | string | `icf` \| `dimension` \| `risk` |
| `action` | string | `click` \| `dismiss` \| `resolve` |

---

### 3.4 实施优先级（不抢 L6 带宽）

| 优先级 | 事件 | 实现位置 | 工时估 |
|--------|------|----------|--------|
| **P0** | E01, E02, E03 | `StagingVoucherReviewDrawer`、Step5 post、向导路由 | 1–2 人日 |
| **P0** | E05, E06 | `AgentChatPage`、`api.agentAssist` 响应后 | 0.5 人日 |
| **P1** | E04, E08 | 证据云页、工作台 | 0.5 人日 |
| **P2** | E07, E08 | parser_engine_dispatcher | 1 人日 |

**Sprint 边界**：埋点 **只写日志表**，不做看板 UI（Week 2 用 SQL 出数）。

---

## 四、Wizard of Oz 两周实验设计

对齐 [sprint-iteration-control-2026-07-12.md](./sprint-iteration-control-2026-07-12.md) §四 两周节奏。

### 4.1 实验总览

```text
目标：在「不扩 Agent / 不扩场景 B」前提下，用数据回答「AI 是否净收益」

对照组：规则/向导/手点（现有 UI）
实验组 A：AI 凭证草稿（真实 LLM，已有）
实验组 B：Agent 路径建议（WoO：后端 100% 规则，前端仍显示「助手」）

样本：≥5 个真实账簿任务（可含你自己的测试账簿）
人数：≥3 名真实用户或扮演用户的业务方
```

### 4.2 Week 1 — 基线 + 埋点 + WoO 启动

| 日 | Sprint 对齐 | 动作 | 产出 |
|----|-------------|------|------|
| **Mon–Tue** | §四 W1 Mon–Tue pytest | 接入 E01/E02/E03/E05；pytest 不回归 | 埋点 PR |
| **Wed** | §四 W1 Wed–Thu L6 | **实验 1**：走完整 L6 路径 A，录屏 + 填人工表（步骤数、耗时） | L6 基线表 |
| **Thu** | 同上 | **实验 2**：同一资料「纯手填凭证」vs「AI 草稿」对比耗时 | 采纳率初值 |
| **Fri** | §四 W1 Fri 合入 | **实验 3**：Agent WoO — `assist` 强制 `source=rules`（配置开关），测路径点击率 | WoO 日志 |

**Week 1 门禁**：L6 阻塞缺陷优先；**禁止**新增 Agent 工具、禁止多 Agent 步骤 UI。

### 4.3 Week 2 — 只读分析 + Go/No-Go

| 日 | Sprint 对齐 | 动作 | 产出 |
|----|-------------|------|------|
| **Mon–Tue** | §四 W2 Mon–Tue L6 修复 | 只修 L6 阻塞；跑 SQL 聚合 KPI | KPI 周报 |
| **Wed** | §四 W2 Wed P2 选一 | 根据 KPI 决定 P2：**证据** or **解析**（不两个都做） | 决策记录 |
| **Thu–Fri** | §四 W2 Thu–Fri 文档 | Go/No-Go 表写入 code-truth；更新 Sprint §三边界 | 结论文档 |

### 4.4 三个 WoO 实验卡

#### 实验 1 — AI 凭证草稿采纳率（P0，真实 AI）

| 项 | 内容 |
|----|------|
| **假设** | AI 草稿减少 Step4 耗时 ≥20%，采纳率 ≥60% |
| **场景** | 场景 A：发票或流水 ≥10 张 |
| **流程** | 上传 → 解析 → 打开草稿 → 保存/入账 |
| **记录** | E01/E02 + 人工备注「是否愿再用」 |
| **失败则** | 收窄到 TOP1 单证；降低 LLM 字段范围；不扩 Agent |
| **成功则** | 写入商业化「上云高档」卖点；本地档仍规则优先 |

#### 实验 2 — Agent 路径建议（WoO，规则后端）

| 项 | 内容 |
|----|------|
| **假设** | 用户愿用「1 轮对话 + 点击路径」代替自己找菜单 |
| **场景** | 3 句标准话术：「没团队怎么开始」「导入凭证从哪进」「看内控待办」 |
| **WoO** | 后端 `assist` 走 `_rules_assist_plan`；**不调用 LLM**（`AGENT_ASSIST_WOO_RULES_ONLY=1`） |
| **记录** | E05/E06；轮次、点击率 |
| **失败则** | **降级** `/agent` 为 onboarding 专用入口；主流程改按钮 |
| **成功则** | 任务内嵌窄助手（非全局聊天）；仍不扩工具白名单 |

#### 实验 3 — 无 AI 任务完成率基线

| 项 | 内容 |
|----|------|
| **假设** | 无 AI 时 L6 完成率 ≥70% 才值得加 AI |
| **场景** | 完整导入任务 ≥3 个 |
| **记录** | E03 漏斗；证据 E04 |
| **失败则** | 先修向导/解析，**暂停一切 AI 投入** |
| **成功则** | AI 只优化瓶颈步骤（Step4 草稿） |

### 4.5 Go / No-Go 决策表（Week 2 Fri）

| 功能 | Go 条件（任一不达标 → No-Go） | No-Go 动作 |
|------|--------------------------------|------------|
| AI 凭证草稿 | 采纳率 ≥60% 且 中位省时 ≥20% | 冻结 LLM 字段扩展；加强规则模板 |
| Agent 助手 | 路径点击率 ≥50% 且 中位轮次 ≤2 | 缩为 onboarding；导航改静态指引 |
| 多 Agent 编排 | **本 Sprint 不 Go** | 维持冻结至 F06/F08 达标 |
| 场景 B LLM | **本 Sprint 不 Go** | 维持 TOP3 场景 A |
| 证据云 | 归档率 ≥50%（3 用户） | 修 UX，不加 AI |

---

## 五、与 Sprint 边界对照（防发散）

| Sprint §三「不做」 | 本验证章程 |
|-------------------|------------|
| Agent 写操作自动执行 | E05 只记只读工具；实验 2 禁止自动写 |
| 流式 SSE 扩面 | 实验不包含合规 SSE 推广 |
| API Phase 2 / DDD 拆包 | 埋点走现有表或单表，不新 API 域 |
| D11 / 固定资产 / 多准则 | 矩阵未列入，不做实验 |
| 新增第 6 条导入链路 | 实验 1 只用 `import-jobs` 主路径 |

| Sprint §二「只做」 | 本验证章程 |
|-------------------|------------|
| 主线 A L6 | 实验 1、3 为核心 |
| 主线 B 证据 | 实验 3 归档率；P2 周三可选 |
| 主线 C 解析 P1 | 实验 1 字段映射；不抢 Week1 前三天 |

---

## 六、人工记录表（Week 1 无看板时用）

### 6.1 L6 单任务记录

| 字段 | 填写 |
|------|------|
| 日期 / 操作人 | |
| job_id | |
| 资料类型 | 序时簿 / 流水 / 发票 |
| Step1→Step5 总分钟 | |
| Step4 停留分钟 | |
| 是否用 AI 草稿 | 是 / 否 |
| 入账是否成功 | 是 / 否 |
| 主观：愿重复此流程 | 1–5 分 |

### 6.2 Agent WoO 单会话记录

| 字段 | 填写 |
|------|------|
| session_id | |
| 用户原话（可摘要） | |
| 推荐路径 | |
| 是否点击 | 是 / 否 |
| 轮次 | |
| 是否更好 than 自己找菜单 | 是 / 否 / 说不清 |

---

## 七、Week 2 KPI 周报模板

```markdown
## AI MVP 周报（YYYY-MM-DD）

### 样本
- 账簿数 / 任务数 / Agent 会话数：

### KPI
| 指标 | 值 | 通过线 | 判定 |
|------|-----|--------|------|
| AI 凭证采纳率 | | ≥60% | |
| AI 任务完成率 | | ≥40% | |
| L6 完成率 | | ≥70% | |
| Agent 路径点击率 | | ≥50% | |
| Agent 中位轮次 | | ≤2 | |

### 决策
- F06 AI 草稿：Go / No-Go
- F08 Agent：Go / No-Go / 缩窄
- 下周 P2 选项：证据 / 解析

### 证据
- SQL 查询或导出文件路径
- L6 录屏链接（如有）
```

---

## 八、文档索引

| 文档 | 关系 |
|------|------|
| [sprint-iteration-control-2026-07-12.md](./sprint-iteration-control-2026-07-12.md) | 两周节奏母文档 |
| [parser-dual-scenario-strategy.md](./parser-dual-scenario-strategy.md) | F02/F11 场景边界 |
| [development-convergence-charter.md](./development-convergence-charter.md) | 防发散 |
| [l6-acceptance-checklist.md](./l6-acceptance-checklist.md) | 实验 1/3 步骤 |
| [bookkeeping-v1-decision-record.md](../../backend/docs/bookkeeping-v1-decision-record.md) | 发布范围 |

---

**维护**：Week 2 Fri 将 KPI 结论回写 [code-truth-status.md](./code-truth-status.md) §五；若 No-Go Agent，同步更新 Sprint §三「Agent」行为冻结说明。

---

## 九、已落地入口（代码真值）

| 入口 | 路径 / 配置 | 说明 |
|------|-------------|------|
| **MVP 验证看板** | 前端 `/mvp-metrics` · 侧栏「MVP 验证看板」 | 五色 KPI 卡片 + 事件计数 + 最近 30 条 |
| **埋点 API** | `POST /api/product-events` | 前端 fire-and-forget 写入 |
| **KPI 聚合** | `GET /api/product-events/mvp-kpi-summary?days=14` | 看板数据源 |
| **Agent WoO** | `backend/.env` → `AGENT_ASSIST_WOO_RULES_ONLY=true` | 实验 2：强制规则后端、不调 LLM |
| **生产建表** | `deploy/fix_legacy_db.py` → `product_events` | 每次 deploy schema 自动创建 |
