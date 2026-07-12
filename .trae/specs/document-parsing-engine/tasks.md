# 原始文件解析引擎 — 任务分解（双场景总纲）

> **Owner**: `document-parsing-engine`  
> **Charter**: [parser-dual-scenario-strategy.md](../../documents/parser-dual-scenario-strategy.md)  
> **Code Truth**: [code-truth-status.md](../../documents/code-truth-status.md)  
> **Status**: active-main（历史 Task 1–7 见文末附录，不作为当前 Sprint）

---

## Sprint A — TOP3 样本托底（P0）

### [ ] Task A1: 序时簿 Excel 样本基线（场景 A）

- **Priority**: P0
- **Depends On**: `adaptive-import-engine` spec
- **Description**:
  - 整理用户样本集 → `samples/top3/journal/`、`invoice/`、`bank/`、`contract/`
  - 定义 TOP3 字段清单：日期、凭证号、摘要、科目、借贷、金额
  - 跑 `file_parser_service.parse_entries` 批量回归
- **Acceptance**:
  - 字段准确率 **≥95%**（样本集 N≥10 家导出格式）
  - 失败样本写入修正规则候选清单
- **Code**: `doc_parsing/file_parser_service.py`, `routes_imports.py`

### [ ] Task A2: 发票样本基线（场景 A 为主）

- **Priority**: P0
- **Depends On**: Task A1（别名表共用）
- **Description**:
  - OFD/XML + 结构化 PDF/Excel 样本 → `samples/invoice/`
  - 验收：销方、购方、号码、日期、价税合计、税额
- **Acceptance**:
  - 结构化样本 **≥90%** 字段准确率
  - 扫描发票（场景 B）单独统计，不阻塞 A 验收
- **Code**: `parser_engine_dispatcher`, `parser_voucher_mapper`

### [ ] Task A3: 银行流水样本基线（场景 A 为主）

- **Priority**: P0
- **Depends On**: Task A1
- **Description**:
  - 网银 CSV/Excel + 部分 PDF 样本 → `samples/bank/`
  - 验收：交易日期、对方户名、摘要、借/贷、金额、余额（如有）
- **Acceptance**:
  - 结构化导出 **≥90%** 字段准确率
- **Code**: `parser_engine`, `parser_voucher_mapper`

### [ ] Task A4: 修正回流最小闭环（UI + API）

- **Priority**: P0
- **Depends On**: Task A1–A3 至少各 1 批失败样本
- **Description**:
  - 解析结果页：字段 + 来源标签（rule / llm / seal / manual）
  - 用户改错 → POST `ParseCorrectionRule` → 下次同型文档自动加载
  - 质量看板：按 doc_type 展示准确率、修正命中率
- **Acceptance**:
  - LLM 不可用时仍可改错并回流（Plan B）
  - `routes_parse_correction.py` 端到端人工走通 1 次
- **Code**: `routes_parse_correction.py`, `correction_loop_service`, 前端 Parser 预览页扩展

---

## Sprint B — 合同三层输出（P1）

### [ ] Task B1: 合同台账字段（场景 B）

- **Priority**: P1
- **Depends On**: `seal-recognition-system` Layer1 可用
- **Description**:
  - 扫描合同样本 → 主体（印章优先）、金额、期限、关键条款摘要
  - 写入 `Contract` + `register_ingestion`
- **Acceptance**:
  - 印章检出率 / 主体回填率单独验收（见 seal spec）
- **Code**: `contract_parser_service`, `_perform_seal_recognition`

### [ ] Task B2: 合同底稿合规段落

- **Priority**: P1
- **Depends On**: Task B1
- **Description**:
  - `contract_deep_analyzer` → 矛盾/缺失/非标条款 → workpaper 段落
- **Acceptance**:
  - 1 份合同样本生成可导出底稿片段（人工判定可用）
- **Code**: `contract_deep_analyzer`, `routes_workpapers.py`

### [ ] Task B3: 合同初步凭证草稿（多草稿）

- **Priority**: P1
- **Depends On**: `govern-ai-voucher-evidence-tags` Task G1
- **Description**:
  - 同一 `business_key` 允许多 draft（合同口径 / 发票口径 / 回款口径）
  - **不自动 post**；预览 → 用户选一
- **Acceptance**:
  - 1 个 business_key 下展示 ≥2 草稿，留痕完整
- **Code**: `parser_voucher_mapper`, `routes_parser_voucher.py`

---

## Sprint C — Plan B 与测试债务（P1）

### [ ] Task C1: LLM 降级路径验收

- **Priority**: P1
- **Depends On**: Task A4
- **Description**:
  - Ollama 关闭时 RULE + 印章仍返回 ParseResult + review_flags
  - 文档化 Plan B 行为
- **Acceptance**:
  - 集成测试或脚本验证降级不 500

### [ ] Task C2: 修复 parser_voucher 测试失败

- **Priority**: P1
- **Depends On**: None
- **Description**:
  - 对齐 `test_parser_voucher_api.py` 与当前 API/schema（code-truth §四：38 failed）
- **Acceptance**:
  - 该模块测试全绿或明确 skip 理由

---

## 附录：历史 Task 1–7（数据库 / 收入准则 / 旧 API）

> 以下任务 **已在代码中部分落地**，checkbox 保留考古记录；**新 Sprint 不以 DB 全表创建为阻塞项**。详细 DB 设计见 `spec.md` 附录。

## [x] Task 1: 数据库表设计与创建
（略，见 git 历史）

## [x] Task 2: 字段别名映射引擎
（略）

## [x] Task 3: 合同解析引擎（收入准则视角）
（略）

## [x] Task 4: 标签向量化存储
（略）

## [x] Task 5: 企业信息管理与关联方识别
（略）

## [x] Task 6: API 接口开发
（略 — 新路径以 `parser-engine` / `parser-voucher` 为准）

## [x] Task 7: 测试与验证
（略 — TOP3 样本验收取代旧「≥80% 覆盖率」为 L6 标准）
