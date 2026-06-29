# 文件解析引擎 Phase 2 集成计划

## 实施背景

**Phase 1 已完成**：创建了完整的解析引擎架构（数据结构、格式识别、类型判断、引擎调度）

**Phase 2 目标**：将新的解析引擎集成到现有导入流程中，保持向后兼容

---

## 当前导入流程分析

### 核心调用链

```
process_import_job()
    │
    ├── 会计凭证文件 (.xlsx, .xls, .csv)
    │   └── _process_accounting_file() → parse_entries()
    │
    └── 原始文件 (.pdf, .txt, .md, .doc, .docx, 图片)
        │
        ├── AI_EVIDENCE_SOURCE_TYPES → _process_ai_register_file()
        │
        └── 其他 → _process_source_file()
            ├── _extract_text_with_ocr() → 文本提取
            ├── classify_document() → 类型识别和解析  ← 集成点
            └── _save_parse_feedback() → 保存结果
```

### 关键集成点

**文件**: [import_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/import_service.py)

**位置**: 第 1042 行
```python
result = classify_document(source_file.storage_path, source_file.filename)
```

**返回类型**: `SourceDocumentResult`（来自 `source_document_service.py`）

---

## 集成策略

### 核心原则

1. **向后兼容**：通过配置开关控制新旧引擎切换，默认关闭新引擎
2. **渐进式集成**：先在 `_process_source_file()` 中集成，后续扩展到其他路径
3. **结果转换**：新引擎返回 `ParseResult`，需要转换为 `SourceDocumentResult` 格式

### 配置开关

使用 Phase 1 新增的配置参数：
- `llm_multi_engine_enabled`: 控制是否启用多LLM引擎对比
- `llm_enable_parallel_parsing`: 控制是否启用双引擎并行

---

## 实施步骤

### Step 1: 创建适配器函数

创建一个适配器函数，将新引擎的 `ParseResult` 转换为 `SourceDocumentResult`，保持与现有代码的兼容性。

### Step 2: 修改 _process_source_file()

在 `_process_source_file()` 函数中，根据配置开关选择使用新引擎还是旧引擎。

### Step 3: 扩展 SUPPORTED_SOURCE_FILE_TYPES

新增对 XML、OFD 文件类型的支持。

### Step 4: 更新 DOCUMENT_TYPE_LABELS

新增工资表、费用单据、收据等文档类型的中文标签。

### Step 5: 单元测试验证

创建集成测试，验证新旧引擎的兼容性。

---

## 代码修改方案

### Step 1: 创建适配器函数

在 `parser_engine_dispatcher.py` 中添加：

```python
def parse_result_to_source_document_result(parse_result: ParseResult, filename: str) -> SourceDocumentResult:
    """
    将新引擎的 ParseResult 转换为旧引擎的 SourceDocumentResult
    
    功能描述：保持向后兼容，使新引擎结果可以无缝集成到现有流程
    业务逻辑：
        - 转换文档类型枚举为字符串
        - 转换数据结构
        - 保持置信度和文本信息
    """
    from app.services.source_document_service import SourceDocumentResult
    
    return SourceDocumentResult(
        document_type=parse_result.document_type.value,
        confidence=parse_result.confidence,
        data=parse_result.data,
        raw_text=parse_result.raw_text,
        file_name=filename,
    )
```

### Step 2: 修改 _process_source_file()

在 `import_service.py` 中修改：

```python
def _process_source_file(db: Session, job: ImportJob, source_file: SourceFile) -> ProcessingResult:
    # ... 现有代码 ...
    
    # 选择解析引擎
    settings = get_settings()
    if settings.llm_multi_engine_enabled or settings.llm_enable_parallel_parsing:
        # 使用新的解析引擎
        from app.services.parser_engine import parse_file
        import asyncio
        
        # 异步调用新引擎（在同步上下文中使用 asyncio.run）
        try:
            parse_result = asyncio.run(parse_file(source_file.storage_path))
            
            # 转换结果格式
            from app.services.parser_engine.parser_engine_dispatcher import parse_result_to_source_document_result
            result = parse_result_to_source_document_result(parse_result, source_file.filename)
        except Exception as e:
            # 新引擎失败，降级到旧引擎
            logger.warning(f"新解析引擎调用失败，降级到旧引擎: {e}")
            result = classify_document(source_file.storage_path, source_file.filename)
    else:
        # 使用旧的解析引擎（默认）
        result = classify_document(source_file.storage_path, source_file.filename)
    
    # ... 后续代码不变 ...
```

### Step 3: 扩展 SUPPORTED_SOURCE_FILE_TYPES

在 `import_service.py` 中修改：

```python
SOURCE_FILE_TYPES = {
    ".pdf", ".txt", ".md", ".doc", ".docx", 
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif",
    ".xml", ".ofd",  # 新增：电子发票标准格式
}
```

### Step 4: 更新 DOCUMENT_TYPE_LABELS

在 `import_service.py` 中修改：

```python
DOCUMENT_TYPE_LABELS = {
    "invoice": "发票",
    "bank_statement": "银行流水",
    "contract": "合同",
    "inventory_receipt": "入库单",
    "salary_table": "工资表",           # 新增
    "expense_document": "费用单据",     # 新增
    "receipt": "收据",                  # 新增
    "general": "通用资料",
}
```

---

## 向后兼容策略

### 降级机制

```
配置开关开启 → 尝试新引擎
    │
    ├── 成功 → 使用新引擎结果
    │
    └── 失败 → 降级到旧引擎（classify_document）
```

### 结果格式兼容

新引擎的 `ParseResult` 通过适配器函数转换为 `SourceDocumentResult`，确保后续代码无需修改。

### 配置默认值

- `llm_multi_engine_enabled = True`（Phase 1 已设置）
- `llm_enable_parallel_parsing = True`（Phase 1 已设置）

**注意**: 默认启用新引擎，但如果 LLM 未配置，新引擎会自动降级到规则引擎。

---

## 风险评估

### 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 新引擎调用失败 | 文件解析失败 | 设置降级机制，失败时自动切换到旧引擎 |
| 异步调用阻塞 | 导入流程变慢 | 设置超时时间，避免无限等待 |
| 结果格式不兼容 | 后续流程出错 | 适配器函数确保格式转换 |

### 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 解析结果不一致 | 用户体验下降 | 通过置信度对比选择最优结果 |
| 新增文件类型未测试 | 解析错误 | 逐步扩展，先测试后启用 |

---

## 验证标准

### 测试用例

1. **配置关闭时**：使用旧引擎，结果与之前一致
2. **配置开启时**：使用新引擎，结果正确
3. **新引擎失败时**：自动降级到旧引擎，结果正确
4. **XML/OFD 文件**：正确识别为发票类型
5. **工资表/费用单据/收据**：正确识别和解析

### 验证方法

```bash
# 运行现有测试
pytest backend/tests/test_import_service.py -v

# 运行新引擎测试
pytest backend/tests/test_parser_engine.py -v
```

---

## 实施顺序

1. ✅ 探索现有服务接口（已完成）
2. ✅ 创建集成计划文档
3. 🔄 创建适配器函数（Step 1）
4. 🔄 修改 _process_source_file()（Step 2）
5. 🔄 扩展文件类型支持（Step 3）
6. 🔄 更新文档类型标签（Step 4）
7. 🔄 单元测试验证（Step 5）

---

**创建日期**: 2026-06-26
**状态**: 计划阶段，待实施
**下一步**: 开始实施 Step 1-5