# 文件解析引擎 Phase 1 实施计划

## 实施背景

**完整规划文档**: [.trae/documents/file-parser-engine-refactor-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/file-parser-engine-refactor-plan.md)

**用户已批准规划**，现在继续执行 Phase 1 基础架构实施。

---

## Phase 1 进度概览

### ✅ 已完成（基础数据结构）

| 任务 | 文件 | 状态 | 说明 |
|------|------|------|------|
| Task 3 | `parser_engine/parse_result.py` | ✅ 完成 | 统一数据结构，定义所有枚举和数据类 |
| Task 1 | `parser_engine/format_recognizer.py` | ✅ 完成 | 格式识别层，支持PDF文字型/图片型检测 |
| Task 2 | `parser_engine/document_type_classifier.py` | ✅ 完成 | 类型判断层，含细分类型识别和冲突处理 |

### ⏳ 待完成（引擎调度层）

| 任务 | 文件 | 状态 | 核心功能 |
|------|------|------|---------|
| Task 4 | `parser_engine/parser_engine_dispatcher.py` | ⏳ 待实施 | 引擎调度层，双引擎并行，多LLM对比，结果融合 |
| Task 6 | `core/config.py` 扩展 | ⏳ 待实施 | 新增LLM性能参数和多LLM引擎对比配置 |
| Task 5 | `parser_engine/__init__.py` | ⏳ 待实施 | 模块初始化和便捷函数导出 |
| Task 7 | 验证基础架构 | ⏳ 待实施 | 测试格式识别和类型判断功能 |

---

## 已完成文件详细说明

### 1. parse_result.py - 统一数据结构

**路径**: [backend/app/services/parser_engine/parse_result.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/parser_engine/parse_result.py)

**核心内容**:
- `FileFormat` 枚举: 支持 PDF_TEXT、PDF_IMAGE、OFD、XML、EXCEL、CSV、IMAGE、TEXT、WORD、MARKDOWN 等 11 种格式
- `DocumentType` 枚举: 支持 INVOICE、BANK_STATEMENT、CONTRACT、INVENTORY_RECEIPT、SALARY_TABLE、EXPENSE_DOCUMENT、RECEIPT 等 7 种主类型
- `DocumentSubType` 枚举: 各主类型下的细分类型（如发票的专用/普通/定额/电子，银行的流水单/对账单/回单等）
- `EngineType` 枚举: RULE、LLM、FUSED、WEIGHTED_VOTE、USER_SELECT
- `ParseResult` 数据类: 统一解析结果结构，包含文档类型、数据、置信度、引擎来源、校验错误、会计建议等
- `LLMComparisonResult` 数据类: 多LLM引擎对比结果，包含各引擎原始结果、字段一致性分析、最终选择结果、字段来源标注
- `FormatRecognitionResult` 数据类: 格式识别结果
- `TypeClassificationResult` 数据类: 类型判断结果
- `UnrecognizedFile` 数据类: 未识别文件对象，支持二次分析

**会计口径设计**:
- 置信度字段用于判断结果可信度
- `validation_errors` 记录会计勾稽关系错误
- `accounting_notes` 提供会计准则级别的处理建议
- 字段来源标注便于审计追溯

---

### 2. format_recognizer.py - 格式识别层

**路径**: [backend/app/services/parser_engine/format_recognizer.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/parser_engine/format_recognizer.py)

**核心内容**:
- `SUFFIX_TO_FORMAT` 映射: 文件后缀到格式的直接映射
- `FormatRecognizer` 类: 格式识别器
  - `recognize()` 方法: 识别文件格式
  - `_detect_pdf_type()` 方法: 检测PDF类型（文字型 vs 图片型）
    - 使用 pdfplumber 提取文本，字符数 < 50 判定为图片型
  - `_can_extract_text_directly()` 方法: 判断是否需要OCR

**技术实现**:
- PDF类型检测只检查前3页，避免处理大文件耗时
- 检测失败时保守假设为图片型（需要OCR）
- 图片型PDF和图片文件标记为 `needs_ocr=True`

---

### 3. document_type_classifier.py - 类型判断层

**路径**: [backend/app/services/parser_engine/document_type_classifier.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/parser_engine/document_type_classifier.py)

**核心内容**:
- `FORMAT_TO_CANDIDATE_TYPES` 映射: 文件格式到候选类型集的映射
  - OFD/XML → 发票（电子发票专用格式）
  - Excel/CSV → 银行流水、工资表、费用单据、会计凭证
  - PDF → 发票、合同、收据
- `TYPE_KEYWORDS` 映射: 各文档类型的关键词映射（用于内容特征判断）
- `DocumentTypeClassifier` 类: 类型判断器
  - `classify()` 方法: 判断文档类型（用户预选优先 → 格式特征 → 内容关键词 → 冲突处理）
  - `_extract_text_for_classification()` 方法: 为类型判断提取文本（只读取前500字符）
  - `_calculate_type_scores()` 方法: 计算各候选类型的匹配得分
  - `_identify_sub_type()` 方法: 细分类型识别总入口
  - 7个细分类型识别方法:
    - `_identify_invoice_sub_type()`: 发票细分（专用/普通/定额/电子/机打）
    - `_identify_bank_sub_type()`: 银行细分（流水单/对账单/回单/余额确认函）
    - `_identify_contract_sub_type()`: 合同细分（标准/简易/手写/模板/订单）
    - `_identify_inventory_sub_type()`: 入库单细分（标准/物流/销售/采购/电商）
    - `_identify_salary_sub_type()`: 工资表细分（标准/简易/提成/详细）
    - `_identify_expense_sub_type()`: 费用单据细分（差旅/招待/办公/交通/培训/行程类）
    - `_identify_receipt_sub_type()`: 收据细分（印刷/手写/收据型发票/内部）

**识别策略**:
- 用户预选优先级最高（置信度=1.0）
- 格式特征缩小候选范围
- 内容关键词计算匹配得分
- 低置信度或类型歧义时标记为需要用户确认
- 细分类型根据内容特征和格式特征综合判断

---

## 待实施任务详细说明

### Task 4: parser_engine_dispatcher.py - 引擎调度层

**路径**: `backend/app/services/parser_engine/parser_engine_dispatcher.py`

**核心功能**:
1. **双引擎并行解析**
   - 规则引擎（RULE）：正则+pandas，速度快，适合标准格式
   - LLM引擎（LLM）：语义理解，精度高，适合非标准格式
   - 并行调用两个引擎，按置信度选择最优结果

2. **多LLM引擎对比**
   - 并行调用多个LLM引擎（Qwen2.5-14B、Qwen2.5-7B、DeepSeek、Kimi等）
   - 实现加权投票算法（按引擎权重计算得分）
   - 字段一致性分析（计算各字段在多引擎中的一致率）
   - 结果融合和字段来源标注

3. **未识别文件处理流程**
   - 遍历所有文档类型进行二次分析
   - 记录分析状态和结果
   - 支持用户手动指定类型

**关键算法**（参考规划文档第2.2.1.2节）:
```python
async def multi_llm_comparison(
    text: str,
    document_type: DocumentType,
    config: MultiLLMConfig
) -> LLMComparisonResult:
    """
    多LLM引擎对比流程
    
    1. 并行调用配置的所有LLM引擎
    2. 收集各引擎解析结果
    3. 进行字段一致性分析
    4. 根据对比策略选择最优结果
    """
```

**依赖关系**:
- 调用 `FormatRecognizer`（格式识别）
- 调用 `DocumentTypeClassifier`（类型判断）
- 调用现有服务:
  - `ocr_service.py`（OCR提取）
  - `llm_client_service.py`（LLM调用）
  - `source_document_service.py`（规则引擎解析）

---

### Task 6: 扩展 config.py - 性能配置参数

**路径**: [backend/app/core/config.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/core/config.py)

**新增配置参数**（参考规划文档第2.2.1节）:

```python
# === LLM 性能参数 ===
llm_max_concurrent_models: int = 1          # 最大并发模型数
llm_memory_limit_mb: int = 8192             # 模型内存限制（MB）
llm_preferred_model: str = "qwen2.5-14b"    # 优先使用的模型
llm_fallback_model: str = "qwen2.5-7b"      # 降级模型
llm_timeout_seconds: int = 30               # 单次调用超时（秒）

# === 并行策略 ===
llm_enable_parallel_parsing: bool = True    # 是否启用双引擎并行
llm_parallel_timeout_seconds: int = 60      # 并行解析总超时（秒）

# === 结果选择策略 ===
llm_result_selection_mode: str = "auto_best"  # auto_best / user_choose / hybrid
llm_confidence_threshold_auto: float = 0.8    # 自动选择的置信度阈值
llm_confidence_threshold_user: float = 0.6    # 需要用户确认的阈值

# === 多LLM引擎对比配置 ===
llm_multi_engine_enabled: bool = True                     # 是否启用多LLM对比
llm_comparison_mode: str = "parallel_all"                 # parallel_all / sequential_fallback / best_two
llm_comparison_strategy: str = "weighted_vote"            # weighted_vote / highest_confidence / intersection / union_llm_best / user_review
llm_comparison_engines: str = "qwen2.5-14b,qwen2.5-7b,deepseek-v2"  # 对比引擎列表
llm_engine_weights: str = '{"qwen2.5-14b":0.40,"qwen2.5-7b":0.25,"deepseek-v2":0.25}'  # 引擎权重（JSON字符串）
llm_agreement_threshold: float = 0.7                      # 字段一致率阈值
llm_save_all_results: bool = True                         # 是否保存所有LLM结果
```

**设计要点**:
- 使用 Pydantic Settings 自动从 `.env` 文件读取配置
- 引擎权重和引擎列表用JSON字符串存储，便于配置和序列化
- 配置分层：系统默认 → `.env` 文件 → 用户偏好（数据库）

---

### Task 5: parser_engine/__init__.py - 模块初始化

**路径**: `backend/app/services/parser_engine/__init__.py`

**核心内容**:
```python
"""
文件解析引擎模块

统一入口，提供便捷的解析函数
"""

from app.services.parser_engine.parse_result import (
    FileFormat,
    DocumentType,
    DocumentSubType,
    EngineType,
    ParseResult,
    LLMComparisonResult,
    FormatRecognitionResult,
    TypeClassificationResult,
    UnrecognizedFile,
)

from app.services.parser_engine.format_recognizer import (
    FormatRecognizer,
    recognize_file_format,
)

from app.services.parser_engine.document_type_classifier import (
    DocumentTypeClassifier,
    classify_document_type,
)

# 引擎调度层（待实施）
from app.services.parser_engine.parser_engine_dispatcher import (
    ParserEngineDispatcher,
    parse_file,  # 便捷函数
)

__all__ = [
    "FileFormat",
    "DocumentType",
    "DocumentSubType",
    "EngineType",
    "ParseResult",
    "LLMComparisonResult",
    "FormatRecognitionResult",
    "TypeClassificationResult",
    "UnrecognizedFile",
    "FormatRecognizer",
    "recognize_file_format",
    "DocumentTypeClassifier",
    "classify_document_type",
    "ParserEngineDispatcher",
    "parse_file",
]
```

**便捷函数设计**:
- `recognize_file_format(file_path)` → 格式识别
- `classify_document_type(file_path, ...)` → 类型判断
- `parse_file(file_path, ...)` → 完整解析流程（格式→类型→引擎调度→结果）

---

### Task 7: 验证基础架构

**验证内容**:

1. **格式识别功能测试**
   - 测试文件: 各种格式的样例文件（PDF文字型、PDF图片型、Excel、CSV、XML、OFD、图片）
   - 验证点: 格式识别准确性、PDF类型检测准确性、OCR标记正确性

2. **类型判断功能测试**
   - 测试文件: 各种文档类型的样例文件
   - 验证点: 类型判断准确性、细分类型识别准确性、冲突处理正确性

3. **数据结构完整性测试**
   - 验证点: 所有枚举完整性、数据类字段完整性、序列化/反序列化正确性

4. **模块导入测试**
   - 验证点: 所有模块可正确导入、便捷函数可正确调用

**测试方法**:
- 创建单元测试文件: `backend/tests/test_parser_engine.py`
- 使用真实的财务文档样例进行测试
- 验证会计口径的准确性

---

## 实施顺序

按照依赖关系和风险等级，建议的实施顺序：

### Phase 1.1: 完成数据层（已完成 ✅）
- ✅ Task 3: parse_result.py
- ✅ Task 1: format_recognizer.py
- ✅ Task 2: document_type_classifier.py

### Phase 1.2: 完成配置层（优先级高）
- ⏳ Task 6: 扩展 config.py
  - 原因: 引擎调度层依赖配置参数

### Phase 1.3: 完成引擎调度层（核心）
- ⏳ Task 4: parser_engine_dispatcher.py
  - 原因: 核心功能，实现双引擎并行和多LLM对比

### Phase 1.4: 完成模块封装
- ⏳ Task 5: parser_engine/__init__.py
  - 原因: 模块初始化，导出便捷函数

### Phase 1.5: 验证和测试
- ⏳ Task 7: 验证基础架构
  - 原因: 确保功能正确性

---

## 技术决策记录

### 决策 1: PDF类型检测阈值
- **决策**: 文本字符数 < 50 判定为图片型PDF
- **原因**: 
  - 典型的文字型PDF每页至少有几十个字符
  - 图片型PDF可能只有少量页码、水印等文字
- **风险**: 
  - 某些特殊PDF可能有少量文字但仍需要OCR
  - 用户可能需要手动指定PDF类型

### 决策 2: 类型判断置信度阈值
- **决策**: 
  - 置信度 < 0.3 → 需要用户确认
  - 置信度差值 < 0.1 → 类型歧义，需要用户确认
- **原因**: 
  - 低置信度表示关键词匹配不足
  - 类型歧义可能导致解析策略错误
- **风险**: 
  - 可能增加用户确认频率
  - 需要在精度和用户体验间平衡

### 决策 3: 细分类型识别策略
- **决策**: 格式特征优先 + 内容关键词辅助
- **原因**: 
  - XML/OFD格式必然是电子发票
  - 内容关键词提供更精确的细分判断
- **风险**: 
  - 某些非标准格式可能识别错误
  - 需要用户手动指定细分类型

### 决策 4: 多LLM引擎对比模式
- **决策**: 并行调用所有配置的引擎 + 加权投票
- **原因**: 
  - 用户要求精度优先
  - 加权投票可以综合各引擎优势
- **风险**: 
  - 并行调用可能增加响应时间
  - 需要合理的超时设置和降级策略

---

## 验证标准（六级完成度）

按照项目任务治理规则，Phase 1 应达到的完成度：

- **L1 文档完成**: ✅ 规划文档已完成，包含详细设计
- **L2 数据模型完成**: ✅ parse_result.py 已完成，包含所有枚举和数据类
- **L3 服务完成**: ⏳ parser_engine_dispatcher.py 待实施
- **L4 API完成**: ⏳ 需要集成到现有导入流程（后续Phase）
- **L5 前端接入完成**: ⏳ 需要前端展示多引擎对比结果（后续Phase）
- **L6 测试与真实数据验证完成**: ⏳ 需要创建测试文件并使用真实财务文档验证

**Phase 1 目标**: 达到 L3 服务完成 + L6 部分验证（基础架构功能验证）

---

## 后续 Phase 规划（简要）

### Phase 2: 集成到现有导入流程
- 修改 `import_service.py`，集成新的解析引擎
- 替换现有的 `source_document_service.py` 调用
- 保持向后兼容，不影响现有功能

### Phase 3: 前端展示优化
- 多引擎对比结果展示界面
- 用户手动选择结果的交互界面
- 未识别文件二次分析界面

### Phase 4: 性能优化和监控
- 引擎性能监控和日志
- 引擎准确率统计和权重调整
- 异步处理和队列管理

---

## 风险提示

1. **技术风险**:
   - 多LLM并行调用可能增加响应时间
   - PDF类型检测可能误判
   - 细分类型识别可能不准确

2. **业务风险**:
   - 未识别文件处理流程可能增加用户操作复杂度
   - 多引擎对比可能增加用户理解成本

3. **兼容性风险**:
   - 新引擎调度层需要兼容现有导入流程
   - 配置参数变更需要考虑现有环境

---

## 实施建议

1. **优先完成配置层**: Task 6 应优先实施，为引擎调度层提供配置基础
2. **渐进式实施**: 先实现双引擎并行，再实现多LLM对比，分步验证
3. **真实数据测试**: 使用真实财务文档样例进行测试，确保会计口径准确性
4. **用户反馈收集**: 实施后收集用户反馈，调整阈值和策略

---

**创建日期**: 2026-06-26
**状态**: Phase 1.1 已完成，Phase 1.2-1.5 待实施
**下一步**: 实施 Task 6（扩展 config.py）