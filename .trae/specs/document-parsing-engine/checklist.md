# 原始文件解析引擎 — 验收清单（双场景总纲）

> **Charter**: [parser-dual-scenario-strategy.md](../../documents/parser-dual-scenario-strategy.md)  
> **Code Truth**: [code-truth-status.md](../../documents/code-truth-status.md)  
> **规则**: 旧项 `[x]` 为历史考古；**当前 Sprint 以「TOP3 + 修正回流」未勾选项为准**

---

## 一、Spec 重构（2026-07-05）

- [x] `document-parsing-engine/spec.md` 升格为 D05 双场景总纲
- [x] `parser-dual-scenario-strategy.md` charter 已写入 documents
- [x] `adaptive-import-engine/spec.md` 收窄为场景 A
- [x] `seal-recognition-system/spec.md` 收窄为场景 B Layer1
- [x] `requirements-domain-index.md` 索引已更新

---

## 二、TOP3 样本通过率（L6 阻塞项）

### 序时簿 / 凭证 Excel（场景 A）

- [ ] 样本集目录与清单已建立（≥10 种导出格式）
- [ ] 批量回归脚本可重复运行
- [ ] 核心字段准确率 **≥95%**
- [ ] 失败样本已录入修正规则候选

### 发票（场景 A 结构化）

- [ ] 样本集已建立（OFD/XML + 结构化 PDF/Excel）
- [ ] 核心字段准确率 **≥90%**
- [ ] 扫描发票（B）单独统计，不混算 A 指标

### 银行流水（场景 A 结构化）

- [ ] 样本集已建立（网银 CSV/Excel）
- [ ] 核心字段准确率 **≥90%**

---

## 三、修正回流（优先级高于双引擎一致性）

- [ ] 解析结果页展示字段来源（rule / llm / seal / manual）
- [ ] 用户改错可保存为 `ParseCorrectionRule`
- [ ] 下次同型文档自动加载修正规则
- [ ] 按 doc_type 质量看板（准确率、修正命中率）
- [ ] LLM 不可用时仍可改错并回流（Plan B 人工路径）

---

## 四、合同三层输出（P1）

- [ ] 台账：主体（印章优先）、金额、期限、条款摘要 → register
- [ ] 底稿：`contract_deep_analyzer` 合规段落可导出
- [ ] 候选草稿：初步分录预览，**不自动 post**
- [ ] 同一 `business_key` 多草稿可选（见 govern-ai spec）

---

## 五、Plan B / 测试

- [ ] Ollama 关闭时 RULE + 印章仍返回有效 ParseResult
- [ ] `test_parser_voucher_api.py` 与当前 API 对齐（全绿或 documented skip）
- [ ] 端到端：1 条记账路径 + 1 条审计路径人工验收记录

---

## 附录：历史验收（考古，勿删）

- [x] 数据库表已创建（contracts, invoices, bank_statements 等）
- [x] 字段别名映射引擎已实现
- [x] 合同解析引擎（收入准则视角）已实现
- [x] 标签向量化存储已实现
- [x] 企业信息 / 关联方识别已实现
- [x] 旧式 POST /api/parse/contract、/api/parse/invoice 可用
- [x] test_document_parsing_api.py 历史用例通过

> 新主路径：`import-jobs` → `parser-engine` → `parser-voucher`；旧 `/api/parse/*` 标记 deprecated。
