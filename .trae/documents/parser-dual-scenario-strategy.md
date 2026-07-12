# 解析引擎双场景策略（Spec 重构 Charter）

> **文档类型**: 规格重构路线图（非新增需求域）  
> **更新日期**: 2026-07-05  
> **Owner Spec**: `document-parsing-engine`（升格为 D05 总纲）  
> **Depends On**: [AGENTS.md](../../AGENTS.md)、[code-truth-status.md](./code-truth-status.md)  
> **Status**: active-refactoring

---

## 一、本文角色

**不是第 61 个 parallel spec**，而是对现有 D05 解析域 specs 的 **总纲重构**：

| 动作 | 说明 |
|------|------|
| **升格** | `document-parsing-engine` 从 `mixed-needs-split` → `active-main`（双场景总纲） |
| **收窄** | 周边 spec 写清 In Scope / Out Scope，避免重复造车 |
| **不新增域** | 仍在 D05；印章、AI 草稿、导入分属依赖 spec |

代码真值见 [code-truth-status.md](./code-truth-status.md)。

---

## 二、核心产品哲学

所有资料类型（发票、银行流水、费用单、工资表、收据、合同、入库单、凭证/序时簿）均存在 **两个世界**：

| 场景 | 代号 | 资料特征 | 解析重点 |
|------|------|----------|----------|
| **电子档案** | **A** | 系统导出、OFD/XML、标准 Excel/PDF；版式因厂商不同但 **字段可预期** | 模板 / 规则 / 别名表；**多样本 → 固定映射** |
| **实体化资料** | **B** | 扫描、拍照、混贴；称呼代全称、**印章代主体**、报价单代条款 | **分层识别** + 语义 + 项目背景；**修正回流 > 双引擎一致性** |

两条路径 **重点不同**，输出 **殊途同归** → 统一结构化事实 → 再分流：

```text
StructuredDocumentFact（统一中间形态）
  ├── 尽调：模块台账 + 底稿（合同合规环节）
  ├── 记账：候选凭证草稿（人工复核后 post）
  └── 风险：先有准确分录，再规则/向量初筛
```

---

## 三、场景 A — 电子档案（结构化托底）

### 3.1 主规格

| Spec | 角色 |
|------|------|
| **`adaptive-import-engine`** | 场景 A **唯一主 spec**（Excel/CSV 表头自适应、模板、质量分） |
| `file_parser_service` | 实现：`parse_entries`、序时簿/凭证批量 |

### 3.2 TOP3 托底（当前 Sprint 验收重点）

| 资料 | 主路径 | 目标 |
|------|--------|------|
| 序时账/科目表 Excel | A：`import-jobs` + `file_parser` | 字段映射 ≥95%，L6 人工验收 |
| 全电/OFD/XML 发票 | A 规则 + 必要时 LLM 补字段 | 台账 + 候选草稿 ≥90% |
| 网银 Excel 流水 | A 列映射 | 台账 + 候选草稿 ≥90% |

### 3.3 Out of Scope（场景 A）

- 印章分层、合同深度语义（属 B）
- 多 LLM 对比（属 B 增强，非 A 阻塞）

---

## 四、场景 B — 实体化资料（分层识别）

### 4.1 固定流水线

```text
Step 0  格式识别（PDF 文字 / 图片 / 扫描）
Step 1  印章层（检测 → 抠图 → OCR → 主体候选）     ← seal-recognition-system
Step 2  格式层（表格、标题、金额日期、编号）       ← RULE / rule_parsers
Step 3  非标层（手写、附件、称呼、隐含条款）       ← LLM + contract_deep_analyzer
Step 4  背景层（项目、账簿、已知往来、科目表）     ← 待系统化注入
Step 5  融合（RULE ∥ LLM ∥ 后期多 LLM；Ollama 挂则降级）
Step 6  统一 ParseResult + review_flags + 人工复核点
Step 7  分流 → 台账 / 底稿 / 候选草稿（不自动 post）
```

### 4.2 主规格分工

| Spec | 场景 B 角色 |
|------|-------------|
| **`document-parsing-engine`** | 总纲：分层、融合、输出模型、样本验收 |
| **`seal-recognition-system`** | **Layer 1 印章**（收窄，不做全文档解析） |
| `govern-ai-voucher-evidence-tags` | 多草稿、证据充分性、复核留痕 |
| `auto-generate-entries-from-source` / parser-voucher | 候选草稿出口（5 类单证 + 合同初步草稿） |

### 4.3 Plan B（LLM 不可用）

- **RULE + 印章结果必须仍可输出**；界面允许人工补字段并 **写入修正规则**。
- 并行引擎目的：**至少一条路径可用**，而非「必须 LLM 成功才返回」。

---

## 五、殊途同归：三类输出

### 5.1 模块台账（尽调）

- 发票 / 流水 / 合同 / 入库等 → `register_ingestion` + 各模块表。
- **合同**：主体、金额、期限、印章、关键条款摘要（CAS 相关字段）。

### 5.2 尽调底稿（合同合规）

- `contract_deep_analyzer`：矛盾、缺失要素、非标条款、会计影响提示。
- 导出至工作底稿文件（Step6 / workpapers 链路）。

### 5.3 候选凭证草稿（记账辅助）

| 资料类型 | 自动草稿 | 说明 |
|----------|----------|------|
| 发票、流水、费用、工资、收据 | ✅ `parser_voucher_mapper` | 预览 → 确认 → draft |
| 合同 | ⚠️ **初步草稿**（非一键正式凭证） | 收入/成本等 **建议分录**，多口径允许多草稿 |
| 入库单 | 台账为主 | 草稿可选、优先级低 |

**多草稿同一业务**（产品目标，分阶段）：

```text
business_key（同一业务事实）
  ├── draft_A：合同口径
  ├── draft_B：发票口径
  └── draft_C：银行回款口径
→ 提示用户「多来源指向同一业务」→ 人工选一或合并 → post
```

数据模型：`business_key`、`source_document_ids`、`draft_role` — 见 `govern-ai-voucher-evidence-tags` 增量 tasks。

---

## 六、修正回流（比双引擎更重要）

### 6.1 产品形态（开发目标）

1. **解析结果页**：字段 + 来源标签（规则/LLM/印章/人工）。
2. **改错保存**：用户改字段 → 写入 `ParseCorrectionRule`。
3. **两类规则库**：
   - **A 库**：别名、列名、Excel 模板（电子）。
   - **B 库**：印章→主体、phrase→字段、LLM 提示片段（实体）。
4. **下次自动套用**；看板：按资料类型 **字段准确率、修正命中率**。
5. **LLM 失败**：仍展示 A/B 库已命中字段 + 人工补全仍可保存修正。

### 6.2 关联代码

- `routes_parse_correction.py`、`ParseCorrectionRule`、`correction_loop_service`
- `parse_quality_metric_service`、质量看板 API

### 6.3 关联 spec 任务

- 写入 `document-parsing-engine/tasks.md`（重构后）
- 不单独新建 `parse-correction` spec

---

## 七、样本驱动功能迭代（非二选一）

**原则**：功能可以优先调整，但 **每轮必须绑定样本通过率**。

| 阶段 | 功能 | 样本 |
|------|------|------|
| 基线 | 记录 TOP3 当前字段准确率 | 每类 ≥30 份（可脱敏） |
| 迭代 | 只改通过率最低字段 | **同一批样本**重跑 |
| A 场景 | 加别名/模板，少加 LLM | 通过率 ≥95% 再扩类型 |
| B 场景 | 印章→主体、非标条款 | **单独统计**，不与 A 混算 |
| 右列勾稽 | 暂不扩功能 | 样本分层标签 + 通过率看板 |

用户已有大量样本 → **立即建立 TOP3 基线表**，写入 `document-parsing-engine/checklist.md`。

---

## 八、Spec 重构映射表

| 现有 Spec | 重构后状态 | In Scope | Out of Scope |
|-----------|------------|----------|--------------|
| **document-parsing-engine** | **active-main 总纲** | 双场景 A/B、分层、输出、样本验收、修正回流 | 具体 API 路径收敛 |
| **adaptive-import-engine** | active-main（A 专用） | Excel/CSV 序时簿、表头自适应 | PDF 合同、印章 |
| **seal-recognition-system** | active-increment | B Layer1 印章 | 全文档 LLM 解析 |
| **govern-ai-voucher-evidence-tags** | active-main | 多草稿、证据、复核 | 解析规则本身 |
| **auto-generate-entries-from-source** | active-increment | 草稿生成策略 | 台账登记 |
| document-parsing-engine 附录 DB 草案 | historical | 参考 | 不作为实施优先级 |
| **新增 planning** | parser-dual-scenario-strategy.md（本文） | 重构 charter | 业务代码 |

**Deprecated 叙述**（写入总纲，不删旧 spec 目录）：

- 旧「双引擎一致性为王」→ 改为「并行可用 + 修正回流为王」。
- 旧「document-parsing-engine 一包打尽」→ 拆到 A/B 子 spec。

---

## 九、执行顺序（与 AGENTS.md §8 对齐）

1. **TOP3 样本基线 + 通过率表**（P0）
2. **场景 A**：序时簿/发票/流水 规则与修正 UI 最小闭环（P0）
3. **场景 B 合同**：台账 + 底稿 + 单条候选草稿（P1）
4. **多草稿 business_key**（P1–P2）
5. **右列勾稽样本库**（P2，不扩新功能）
6. ~~新 seal Agent API~~ — 冻结至 TOP3 达标

---

## 十、验收标准（总纲级）

| 项 | 标准 |
|----|------|
| TOP3 场景 A | 固定样本集字段准确率 ≥95%（序时簿）/ ≥90%（发票/流水） |
| 合同场景 B | 台账必填字段 ≥85%；底稿合规段落可导出；候选草稿可预览 |
| 修正回流 | 同版式第二次解析修正规则命中率 ≥70% |
| Plan B | Ollama 不可用时 RULE+印章+人工补字段流程可完成 |
| 文档 | 无 spec checklist 与 code-truth-status 冲突 |

---

## 十一、相关文档

| 文档 | 关系 |
|------|------|
| [document-parsing-engine/spec.md](../specs/document-parsing-engine/spec.md) | 总纲正文（已插入双场景章节） |
| [adaptive-import-engine/spec.md](../specs/adaptive-import-engine/spec.md) | 场景 A |
| [seal-recognition-system/spec.md](../specs/seal-recognition-system/spec.md) | 场景 B Layer1 |
| [govern-ai-voucher-evidence-tags/spec.md](../specs/govern-ai-voucher-evidence-tags/spec.md) | 多草稿与证据 |
| [api-boundary-governance-plan.md](./api-boundary-governance-plan.md) | API 主路径（非本文重点） |
