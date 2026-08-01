# 经济事件工单（Economic Event Workorder）— 正式规格

> **状态**: active-main（正式规格 · 待分阶段实施）  
> **需求域**: D14 经济事件与事件工单  
> **验收层级目标**: 阶段 1 → L4–L5；阶段 3 → 与 Agent 联调后达 L5  
> **依赖**: D04 凭证生命周期、D09 Tag/向量、D05 导入解析、D01 权限；**不替代** L6 记账验收  
> **对齐讨论口径**: 查是问；事件是办（工单，必有状态/数据变化意图）  
> **OS 总纲**: [ai-native-finance-os-definition.md](../../documents/ai-native-finance-os-definition.md)

---

## 1. Overview

### 1.1 Summary

在现有「分录 + Tag + 证据」之上，增加一等公民对象 **经济事件（Economic Event）**，产品形态为 **事件工单**：

- 表达「企业发生了 / 要办理哪一件事」
- 聚合多分录、多 Tag、多证据
- 以 **事件事务（状态机）** 推进：草稿 → … → 已入账 / 已关闭 / 失败待处理
- 人、导入流程、Agent 均可触发；**写操作逐步挂到事件上**

### 1.2 Purpose

| 目标 | 说明 |
|------|------|
| 可理解 | AI 与人先看见「故事」，再看见「账」 |
| 可执行 | Agent 编排对象是工单状态，不是裸改库 |
| 可审计 | 每步 API、参数、操作人、模型版本可追溯 |
| 不破坏底线 | 金额/借贷/科目仍只在 `AccountingEntry`；Tag 不存钱 |

### 1.3 Target Users

- 会计：按事件复核、入账  
- 审计：按事件抽查证据链  
- 管理层：按事件看业务闭环  
- Agent：把自然语言意图落成工单再调 API  

### 1.4 Non-Goals（本规格明确不做）

- 不做第二套总账（事件不存借贷金额）
- 不把只读查询建成事件工单
- 不在本规格内实现税局直连、固定资产全生命周期、多准则内核
- 不替代 `transactional-design` 中的数据库 ACID（事件事务 **包含** 多次 DB 事务）
- **不阻塞** 记账 v1.0 L6 签字（阶段 1 可与 L6 并行准备，但 L6 路径 A 仍以现有 Step 为准）

---

## 2. 定义

### 2.1 经济事件

> 一条可叙述、可归属账簿、可关联证据与分录的 **企业经济活动意图或结果**。

### 2.2 事件工单

> 经济事件在系统中的 **产品形态**：带编号、类型、状态、负责人、进度时间轴的工单卡片。

### 2.3 事件事务

> 围绕一张工单的 **业务事务**：多步骤调用受控 API；关键步可要求人工审批；失败可停在可解释状态；全程留痕。

### 2.4 与查询的边界

| | 查询 | 事件工单 |
|--|------|----------|
| 意图 | 问 / 看 | 办 / 改状态 |
| 是否改企业状态 | 否 | 是（或明确准备改） |
| 是否开工单 | 否 | 是 |
| Agent | 可直接答 | 必须开/推进工单 |

口诀：**查是问；事件是办。**

---

## 3. 产品形态（画面）

### 3.1 主形态：事件卡片 + 详情页

- 列表/看板：编号、标题、类型、状态、金额合计（派生自关联分录）、证据数、分录数  
- 详情：叙事信息 + Tags + 证据 + 关联凭证/分录 + 状态时间轴 + 操作按钮  

路由建议（阶段 1）：

- `/ledger/events` 列表  
- `/ledger/events/:id` 详情  

### 3.2 过程形态：状态时间轴

默认状态机（可配置扩展，首版固定）：

```text
draft          草稿
collecting     归集中（挂分录/证据）
pending_review 待复核
pending_post   待入账/待审批
posted         已入账
closed         已关闭
failed         失败待处理
cancelled      已取消
```

### 3.3 嵌入形态（不推翻 Step1–5）

| 现有位置 | 嵌入方式 |
|----------|----------|
| 凭证/分录列表 | 显示「所属事件 E-xxx」 |
| Step4 | 可选「按事件分组复核」 |
| 证据云 | 归档目标可选「绑定事件」 |
| Agent | 执行结果落地为事件草稿卡 |

---

## 4. 触发方式（均开启同一类事件事务）

| 触发源 | 行为 |
|--------|------|
| 人工 | 新建工单 / 点「确认入账」等 |
| 导入流程 | 聚类建议「生成 N 个事件」→ 人确认 |
| Agent | 自然语言 → 创建/推进草稿工单 → **禁止**跳过审批直接过账（默认） |

---

## 5. 数据模型（阶段 1 最小集）

### 5.1 `economic_events`

| 字段 | 说明 |
|------|------|
| id / event_no | 主键 / 业务编号 |
| ledger_id | 必填，账簿隔离 |
| title | 事件标题 |
| event_type | 如 `revenue_recognition` / `purchase` / `receipt` / `manual` / `import_cluster` |
| status | 见状态机 |
| occurred_on | 业务发生日 |
| summary | 可检索叙述文本（供向量） |
| created_by / assignee_user_id | 创建人 / 负责人 |
| source | `manual` / `import` / `agent` |
| created_at / updated_at | 时间戳 |

### 5.2 关联表

| 表 | 关系 |
|----|------|
| `economic_event_entries` | event_id ↔ accounting_entry_id（多对多或一对多） |
| `economic_event_files` | event_id ↔ source_file_id |
| `economic_event_steps` | 步骤日志：step_code、api_name、payload_digest、result、actor、model_version、created_at |

**禁止**：在事件表存储 debit/credit 金额作为核算事实（可存冗余展示字段 `display_amount`，以关联分录汇总为准）。

### 5.3 Tag

- 事件可 **汇总展示** 关联分录上的 EntryTag  
- 阶段 2+ 可增加事件级 Tag；不得突破 Tag 不存金额底线  

---

## 6. API 边界（事件型主入口）

阶段 1 建议前缀：`/api/economic-events`

| 能力 | 方法（示意） | 说明 |
|------|--------------|------|
| 创建草稿 | POST `/` | 开工单 |
| 详情/列表 | GET | 按 ledger 过滤 |
| 挂分录 | POST `/{id}/entries` | 关联已有分录 |
| 挂证据 | POST `/{id}/files` | 关联文件 |
| 推进状态 | POST `/{id}/transition` | 校验状态机 + 权限 |
| 步骤日志 | GET `/{id}/steps` | 审计轨迹 |

**原则**：过账、生成凭证仍调用既有 vouchers/entries API；事件层只编排与记录。  
**治理**：新增能力优先挂事件 API，避免再开平行「第三套导入链」。

---

## 7. 分阶段交付

| 阶段 | 名称 | 交付物 | 验收画面 |
|------|------|--------|----------|
| **E0** | 规格冻结 | 本文 + OS 定义文档 | 决策确认 |
| **E1** | 事件壳 | 表 + API + 列表/详情页 | 能打开事件卡并挂分录/证据 |
| **E2** | 导入聚类 | 规则聚类 + 可选 LLM 命名 | 导入后建议生成事件，人确认 |
| **E3** | Agent 驱动 | Agent 只开/推工单再调 Tool | 「办合同」→ 草稿工单 → 待审批 |
| **E4** | 事件向量 | summary 入 Qdrant | 相似历史事件推荐 |

**推荐顺序**：E0 →（并行 L6）→ E1 → E2 → API 收敛若干主路径 → E3 → E4。

---

## 8. 验收标准（E1）

- [ ] 可为指定 ledger 创建事件工单  
- [ ] 可关联 ≥1 分录与 ≥1 文件  
- [ ] 状态可按允许边迁移，非法迁移被拒  
- [ ] 关键推进写入 `economic_event_steps`  
- [ ] 查询类接口 **不** 自动创建事件  
- [ ] 金额展示与关联分录汇总一致；库内无「事件借贷主数据」  
- [ ] schema 变更同步 Alembic + `fix_legacy_db.py`，生产须 schema 审计 PASS  

---

## 9. 风险与约束

| 风险 | 缓解 |
|------|------|
| 与 Step 流程两套入口混淆 | E1 仅增量嵌入，不强制改 L6 路径 A |
| API 继续膨胀 | 事件 API 作编排层；禁止并行新导入链 |
| Agent 绕过审批 | 默认 `pending_post` 需人审；高风险 Tool 只建议 |
| 文档/实现漂移 | 以本文 + code-truth 为准 |

---

## 10. 关联文档

- [ai-native-finance-os-definition.md](../../documents/ai-native-finance-os-definition.md)  
- [tag-vs-account-hierarchy.md](../../../backend/docs/tag-vs-account-hierarchy.md)  
- [development-convergence-charter.md](../../documents/development-convergence-charter.md)  
- [bookkeeping-v1-decision-record.md](../../../backend/docs/bookkeeping-v1-decision-record.md)  
- [agent-lightweight-llm-api/spec.md](../agent-lightweight-llm-api/spec.md)  
- [transactional-design/spec.md](../transactional-design/spec.md)（DB ACID；本规格为业务事务）  
