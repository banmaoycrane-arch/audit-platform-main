# 文件解析引擎重构规划

## 概述

**目标**：重构文件解析引擎，建立统一的"格式识别 → 类型判断 → 引擎调度 → 结果融合"架构，支持所有财务文档的准则级别深度解析。

**核心原则**：
- 精度优先，速度次要（利用本地LLM降低成本）
- 格式+内容双验证，冲突时用户确认
- 双引擎并行（规则+LLM），置信度选择最优结果

---

## 一、现状分析

### 1.1 现有解析服务分布

| 服务文件 | 功能 | 支持文档类型 | 技术栈 |
|---------|------|------------|-------|
| `source_document_service.py` | 原始资料解析 | 发票、银行流水、合同、入库单 | pdfplumber + OCR + pandas + 正则 |
| `contract_parser_service.py` | 合同深度解析（CAS 14） | 合同 | LLM + 会计准则规则 |
| `file_parser_service.py` | 会计凭证解析 | 凭证序时簿 | pandas + 自适应模板 |
| `ocr_service.py` | OCR提取 | 图片型PDF、图片 | EasyOCR / pytesseract |
| `llm_client_service.py` | LLM调用 | - | OpenAI-compatible API（支持Ollama） |
| `import_service.py` | 导入流程集成 | 所有类型 | 调度上述服务 |

### 1.2 存在问题

1. **类型识别分散**：文件格式判断、内容关键词识别、置信度计算散落在不同服务
2. **引擎协作不清晰**：规则解析和LLM解析没有明确的并行/选择机制
3. **缺失文档类型**：工资表、费用单据、收据凭证等业务常用单据未支持
4. **深度解析不足**：除合同（CAS 14）外，其他文档仅做基础字段提取
5. **冲突处理缺失**：格式判断与内容特征不一致时无用户确认机制

---

## 二、性能配置模块设计（新增）

### 2.1 配置模块概述

**目标**：为项目增加性能配置模块，让用户可以控制：
1. LLM模型的运行参数（并发数、内存限制、模型选择等）
2. 解析结果的处理方式（自动选择 vs 用户手动选择）

**设计原则**：
- 配置分层：系统默认配置 → 项目级配置 → 用户偏好配置
- 配置可持久化：存储在数据库中，跨会话保持
- 前端可调节：提供配置界面，用户可随时调整

---

### 2.2 配置参数设计

#### 2.2.1 LLM性能参数

```python
class LLMPerformanceConfig:
    """LLM性能配置"""
    
    # 模型运行参数
    max_concurrent_models: int = 1          # 最大并发模型数（同时运行的LLM数量）
    model_memory_limit_mb: int = 8192       # 模型内存限制（MB），超过则降级
    preferred_model: str = "qwen2.5-14b"    # 优先使用的模型
    fallback_model: str = "qwen2.5-7b"      # 降级模型（内存不足时）
    model_timeout_seconds: int = 30         # 单次调用超时（秒）
    
    # 并行策略
    enable_parallel_parsing: bool = True    # 是否启用双引擎并行解析
    parallel_timeout_seconds: int = 60      # 并行解析总超时（秒）
    
    # 结果选择策略
    result_selection_mode: str = "auto_best"  # 结果选择模式
    # - "auto_best": 自动选择置信度最高的结果
    # - "user_choose": 对比后让用户选择
    # - "hybrid": 高置信度自动选择，低置信度让用户选择
    confidence_threshold_auto: float = 0.8  # 自动选择的置信度阈值
    confidence_threshold_user: float = 0.6  # 需要用户确认的置信度阈值
```

---

#### 2.2.1.1 多LLM引擎对比配置（新增）

**设计目标**：支持同时调用多个LLM引擎，对比不同引擎的解析结果，提高精度

```python
class MultiLLMConfig:
    """多LLM引擎对比配置"""
    
    # 多引擎启用开关
    enable_multi_llm_comparison: bool = True  # 是否启用多LLM引擎对比
    
    # 可用引擎列表
    available_engines: list[str] = [
        "qwen2.5-14b",      # 阿里通义千问 14B（精度最高）
        "qwen2.5-7b",       # 阿里通义千问 7B（速度更快）
        "deepseek-v2",      # DeepSeek V2（逻辑推理强）
        "glm4-9b",          # 智谱GLM-4（中文理解好）
        "kimi",             # Moonshot Kimi（API调用）
        "gpt-4o-mini",      # OpenAI GPT-4o-mini（API调用）
    ]
    
    # 对比模式
    comparison_mode: str = "parallel_all"  # 对比模式
    # - "parallel_all": 并行调用所有配置的引擎，对比结果
    # - "sequential_fallback": 先调用主引擎，失败时依次降级
    # - "best_two": 只对比两个效果最好的引擎
    # - "custom": 用户自定义对比组合
    
    # 对比引擎选择（用户可配置）
    comparison_engines: list[str] = [
        "qwen2.5-14b",      # 主引擎（本地）
        "deepseek-v2",      # 对比引擎（本地）
        "kimi",             # 外部API验证（可选）
    ]
    
    # 对比策略
    comparison_strategy: str = "weighted_vote"  # 对比策略
    # - "weighted_vote": 加权投票（根据各引擎历史准确率）
    # - "highest_confidence": 选择置信度最高的结果
    # - "intersection": 只取各引擎一致的字段
    # - "union_llm_best": LLM结果合并，标注来源
    # - "user_review": 多结果展示，用户选择
    
    # 权重配置（用于加权投票）
    engine_weights: dict[str, float] = {
        "qwen2.5-14b": 0.40,    # 14B模型权重最高
        "qwen2.5-7b": 0.25,     # 7B模型次高
        "deepseek-v2": 0.25,    # DeepSeek逻辑能力强
        "kimi": 0.10,           # 外部API验证权重较低
    }
    
    # 一致性阈值
    agreement_threshold: float = 0.7  # 字段一致率阈值（高于此值自动采纳）
    
    # 结果保存
    save_all_llm_results: bool = True  # 是否保存所有LLM结果（用于后续分析）
    save_comparison_log: bool = True   # 是否保存对比日志
```

---

#### 2.2.1.2 多LLM引擎对比流程

**对比流程架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                    多LLM引擎对比层                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  输入：文件文本 + 文档类型                                    │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │               引擎并行调用                              │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │ │
│  │  │Qwen14B  │ │Qwen7B   │ │DeepSeek │ │Kimi API │      │ │
│  │  │(本地)   │ │(本地)   │ │(本地)   │ │(外部)   │      │ │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘      │ │
│  │       ↓           ↓           ↓           ↓           │ │
│  │  Result_A    Result_B    Result_C    Result_D         │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │               结果对比融合                              │ │
│  │                                                       │ │
│  │  1. 字段一致性检测                                     │ │
│  │  2. 置信度对比                                         │ │
│  │  3. 加权投票                                           │ │
│  │  4. 来源标注                                           │ │
│  │                                                       │ │
│  │  输出：FusedResult（包含各引擎结果 + 最终选择）         │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**对比流程代码示例**：

```python
@dataclass
class LLMComparisonResult:
    """多LLM引擎对比结果"""
    
    # 各引擎原始结果
    engine_results: dict[str, ParseResult]  # {"qwen2.5-14b": Result_A, ...}
    
    # 字段一致性分析
    field_agreement: dict[str, float]  # {"发票号码": 0.75, "金额": 1.0, ...}
    
    # 最终选择结果
    final_result: ParseResult
    
    # 选择依据
    selection_reason: str  # "加权投票" / "置信度最高" / "用户选择"
    
    # 引擎来源标注
    field_sources: dict[str, str]  # {"发票号码": "qwen2.5-14b", ...}


async def multi_llm_comparison(
    text: str,
    document_type: DocumentType,
    config: MultiLLMConfig
) -> LLMComparisonResult:
    """
    多LLM引擎对比流程
    
    流程：
    1. 并行调用配置的所有LLM引擎
    2. 收集各引擎解析结果
    3. 进行字段一致性分析
    4. 根据对比策略选择最优结果
    """
    
    # 1. 并行调用所有引擎
    engine_tasks = []
    for engine_name in config.comparison_engines:
        task = asyncio.create_task(
            call_llm_engine(engine_name, text, document_type)
        )
        engine_tasks.append((engine_name, task))
    
    # 2. 收集结果
    engine_results = {}
    for engine_name, task in engine_tasks:
        try:
            result = await asyncio.wait_for(task, timeout=config.timeout_seconds)
            engine_results[engine_name] = result
        except asyncio.TimeoutError:
            engine_results[engine_name] = None  # 记录超时
    
    # 3. 字段一致性分析
    field_agreement = calculate_field_agreement(engine_results)
    
    # 4. 根据策略选择结果
    if config.comparison_strategy == "weighted_vote":
        final_result = weighted_vote_selection(engine_results, config.engine_weights)
    elif config.comparison_strategy == "highest_confidence":
        final_result = max(engine_results.values(), key=lambda r: r.confidence)
    elif config.comparison_strategy == "intersection":
        final_result = intersection_selection(engine_results)
    elif config.comparison_strategy == "user_review":
        # 返回所有结果，前端让用户选择
        return LLMComparisonResult(
            engine_results=engine_results,
            field_agreement=field_agreement,
            final_result=None,  # 待用户选择
            selection_reason="等待用户选择",
            field_sources={}
        )
    
    # 5. 标注字段来源
    field_sources = determine_field_sources(engine_results, final_result)
    
    return LLMComparisonResult(
        engine_results=engine_results,
        field_agreement=field_agreement,
        final_result=final_result,
        selection_reason=config.comparison_strategy,
        field_sources=field_sources
    )


def calculate_field_agreement(results: dict[str, ParseResult]) -> dict[str, float]:
    """
    计算各字段的一致性率
    
    例如：发票号码在4个引擎中3个一致 → 75%一致率
    """
    agreement = {}
    
    # 获取所有字段名
    all_fields = set()
    for result in results.values():
        if result:
            all_fields.update(result.data.keys())
    
    # 计算每个字段的一致性
    for field in all_fields:
        values = []
        for result in results.values():
            if result and field in result.data:
                values.append(result.data[field])
        
        if len(values) > 1:
            # 计算一致性率（相同值的比例）
            unique_values = set(str(v) for v in values)
            max_count = max(sum(1 for v in values if str(v) == uv) for uv in unique_values)
            agreement[field] = max_count / len(values)
        else:
            agreement[field] = 1.0 if values else 0.0
    
    return agreement


def weighted_vote_selection(
    results: dict[str, ParseResult],
    weights: dict[str, float]
) -> ParseResult:
    """
    加权投票选择最优结果
    
    算法：
    1. 对于每个字段，统计各引擎给出的值
    2. 按引擎权重计算每个值的加权得分
    3. 选择得分最高的值
    4. 合成最终结果
    """
    
    final_data = {}
    final_confidence = 0.0
    
    # 获取所有字段名
    all_fields = set()
    for engine_name, result in results.items():
        if result:
            all_fields.update(result.data.keys())
    
    # 对每个字段进行加权投票
    for field in all_fields:
        value_scores = {}
        
        for engine_name, result in results.items():
            if result and field in result.data:
                value = str(result.data[field])
                weight = weights.get(engine_name, 0.25)
                value_scores[value] = value_scores.get(value, 0) + weight
        
        # 选择得分最高的值
        best_value = max(value_scores.keys(), key=lambda v: value_scores[v])
        
        # 找到给出该值的引擎，使用其原始数据类型
        for engine_name, result in results.items():
            if result and field in result.data:
                if str(result.data[field]) == best_value:
                    final_data[field] = result.data[field]
                    break
    
    # 计算综合置信度（加权平均）
    total_weight = 0.0
    weighted_confidence = 0.0
    for engine_name, result in results.items():
        if result:
            weight = weights.get(engine_name, 0.25)
            weighted_confidence += result.confidence * weight
            total_weight += weight
    
    final_confidence = weighted_confidence / total_weight if total_weight > 0 else 0.0
    
    return ParseResult(
        document_type=results.get(list(results.keys())[0]).document_type,
        data=final_data,
        confidence=final_confidence,
        engine="weighted_vote",
        raw_text="",  # 不重复保存
        validation_errors=[],
        accounting_notes=""
    )
```

---

#### 2.2.1.3 多LLM引擎对比前端展示

**对比结果展示界面**：

```
┌─────────────────────────────────────────────────────────────┐
│              多引擎解析对比结果                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  文件：工资表_2024-01.xlsx                                  │
│  文档类型：工资表                                            │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  字段一致性分析                                         │ │
│  │  ───────────────────────────────────────────────────  │ │
│  │  工资期间：100% ✓ (4引擎一致)                           │ │
│  │  员工数：100% ✓ (4引擎一致)                             │ │
│  │  工资总额：75% ⚠ (3引擎一致，1引擎偏差)                 │ │
│  │  个税合计：50% ⚠ (2引擎一致，2引擎缺失)                 │ │
│  │  社保合计：50% ⚠ (2引擎一致，2引擎缺失)                 │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────┬──────────────┬──────────────┬──────────┐ │
│  │  Qwen2.5-14B │  Qwen2.5-7B  │  DeepSeek V2 │  Kimi    │ │
│  │  (权重0.40)  │  (权重0.25)  │  (权重0.25)  │(权重0.10)│ │
│  ├──────────────┼──────────────┼──────────────┼──────────┤ │
│  │ 置信度：0.92 │ 置信度：0.85 │ 置信度：0.88 │置信度:0.78│ │
│  │              │              │              │          │ │
│  │ 工资期间:    │ 工资期间:    │ 工资期间:    │工资期间: │ │
│  │ 2024-01 ✓   │ 2024-01 ✓   │ 2024-01 ✓   │2024-01 ✓│ │
│  │              │              │              │          │ │
│  │ 员工数：5 ✓ │ 员工数：5 ✓ │ 员工数：5 ✓ │员工数：5 ✓│ │
│  │              │              │              │          │ │
│  │ 工资总额：   │ 工资总额：   │ 工资总额：   │工资总额：│ │
│  │ 35,000 ✓    │ 35,000 ✓    │ 35,000 ✓    │35,500 ✗  │ │
│  │              │              │              │          │ │
│  │ 个税：2,580 ✓│ 个税：缺失   │ 个税：2,580 ✓│个税：缺失│ │
│  │              │              │              │          │ │
│  │ 社保：3,500 ✓│ 社保：缺失   │ 社保：3,600 ✗│社保：缺失│ │
│  └──────────────┴──────────────┴──────────────┴──────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  最终结果（加权投票）                                   │ │
│  │  ───────────────────────────────────────────────────  │ │
│  │  工资期间：2024-01    ← 来源: Qwen2.5-14B              │ │
│  │  员工数：5            ← 来源: Qwen2.5-14B              │ │
│  │  工资总额：35,000     ← 来源: 加权投票(得分0.90)       │ │
│  │  个税合计：2,580      ← 来源: 加权投票(得分0.65)       │ │
│  │  社保合计：3,500      ← 来源: 加权投票(得分0.40) ⚠     │ │
│  │                                                       │ │
│  │  综合置信度：0.86                                     │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  [采用加权投票结果] [查看详细对比] [人工复核低一致字段]      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

#### 2.2.1.4 多LLM引擎对比配置参数（Settings扩展）

```python
class Settings(BaseSettings):
    # ... 现有参数 ...
    
    # === 多LLM引擎对比配置（新增）===
    
    # 多引擎启用
    llm_multi_engine_enabled: bool = True
    llm_comparison_mode: str = "parallel_all"  # parallel_all | best_two | custom
    llm_comparison_strategy: str = "weighted_vote"  # weighted_vote | highest_confidence | user_review
    
    # 对比引擎列表
    llm_comparison_engines: str = "qwen2.5-14b,qwen2.5-7b,deepseek-v2"  #逗号分隔
    
    # 权重配置（JSON格式字符串）
    llm_engine_weights: str = '{"qwen2.5-14b":0.40,"qwen2.5-7b":0.25,"deepseek-v2":0.25}'
    
    # 一致性阈值
    llm_agreement_threshold: float = 0.7
    
    # 外部API配置（可选）
    llm_kimi_api_key: str = ""
    llm_kimi_base_url: str = "https://api.moonshot.cn/v1"
    llm_openai_api_key: str = ""
    llm_openai_base_url: str = "https://api.openai.com/v1"
```

#### 2.2.2 OCR性能参数

```python
class OCRPerformanceConfig:
    """OCR性能配置"""
    
    # OCR引擎选择
    preferred_ocr_engine: str = "easyocr"   # 优先使用的OCR引擎
    # - "easyocr": EasyOCR（多语言支持）
    # - "pytesseract": Tesseract OCR（配合pdf2image）
    # - "paddleocr": PaddleOCR（中文效果好）
    
    ocr_fallback_enabled: bool = True       # 是否启用OCR降级（失败时切换引擎）
    
    # OCR性能参数
    ocr_dpi: int = 200                      # PDF转图片的DPI（影响清晰度和速度）
    ocr_timeout_seconds: int = 10           # 单页OCR超时（秒）
    ocr_max_pages: int = 50                 # 最大处理页数（超过则提示）
```

#### 2.2.3 解析结果处理参数

```python
class ParseResultConfig:
    """解析结果处理配置"""
    
    # 结果展示模式
    result_display_mode: str = "detailed"   # 结果展示模式
    # - "simple": 只显示最终结果
    # - "detailed": 显示双引擎对比详情（规则 vs LLM）
    # - "accounting": 按会计准则维度展示
    
    # 对比展示参数
    show_confidence_scores: bool = True     # 是否显示各引擎置信度
    show_engine_source: bool = True         # 是否标注字段来源引擎
    show_validation_errors: bool = True     # 是否显示校验错误
    
    # 用户选择界面
    enable_user_selection: bool = False     # 是否启用用户手动选择界面
    selection_timeout_seconds: int = 300    # 用户选择等待超时（秒）
    
    # 结果保存策略
    save_both_results: bool = False         # 是否保存双引擎结果（用于分析）
    save_raw_text: bool = True              # 是否保存原始文本
```

---

### 2.3 配置集成方案

#### 2.3.1 扩展 Settings 类（config.py）

**新增参数**：

```python
class Settings(BaseSettings):
    # ... 现有参数 ...
    
    # === 性能配置模块（新增）===
    
    # LLM 性能参数
    llm_max_concurrent_models: int = 1
    llm_memory_limit_mb: int = 8192
    llm_preferred_model: str = "qwen2.5-14b"
    llm_fallback_model: str = "qwen2.5-7b"
    llm_timeout_seconds: int = 30
    llm_parallel_enabled: bool = True
    llm_parallel_timeout: int = 60
    
    # 结果选择模式
    parse_result_mode: str = "auto_best"  # auto_best | user_choose | hybrid
    parse_confidence_threshold_auto: float = 0.8
    parse_confidence_threshold_user: float = 0.6
    
    # OCR 性能参数
    ocr_engine: str = "easyocr"  # easyocr | pytesseract | paddleocr
    ocr_dpi: int = 200
    ocr_timeout: int = 10
    
    # 结果展示参数
    parse_display_mode: str = "detailed"
    parse_show_engine_source: bool = True
    parse_save_both_results: bool = False
```

#### 2.3.2 数据库持久化（可选）

**新增表：performance_configs**

```sql
CREATE TABLE performance_configs (
    id INTEGER PRIMARY KEY,
    organization_id INTEGER NOT NULL,        -- 所属组织/项目
    user_id INTEGER,                         -- 用户偏好（可选）
    
    -- LLM 参数
    llm_max_concurrent_models INTEGER DEFAULT 1,
    llm_memory_limit_mb INTEGER DEFAULT 8192,
    llm_preferred_model VARCHAR(100) DEFAULT 'qwen2.5-14b',
    llm_fallback_model VARCHAR(100) DEFAULT 'qwen2.5-7b',
    
    -- 结果选择模式
    parse_result_mode VARCHAR(20) DEFAULT 'auto_best',
    parse_confidence_threshold_auto REAL DEFAULT 0.8,
    parse_confidence_threshold_user REAL DEFAULT 0.6,
    
    -- OCR 参数
    ocr_engine VARCHAR(20) DEFAULT 'easyocr',
    ocr_dpi INTEGER DEFAULT 200,
    
    -- 创建/更新时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### 2.3.3 API 接口设计

**新增路由：routes_performance_config.py**

```python
@router.get("/performance/config")
def get_performance_config(
    organization_id: int,
    user_id: int | None = None,
    db: Session = Depends(get_db)
) -> PerformanceConfigResponse:
    """获取性能配置（优先返回用户偏好，其次项目配置，最后系统默认）"""
    pass

@router.put("/performance/config")
def update_performance_config(
    payload: PerformanceConfigUpdate,
    db: Session = Depends(get_db)
) -> PerformanceConfigResponse:
    """更新性能配置"""
    pass

@router.post("/performance/test")
def test_performance_config(
    payload: PerformanceTestRequest,
    db: Session = Depends(get_db)
) -> PerformanceTestResponse:
    """测试当前配置的性能（模拟解析单份文档）"""
    pass
```

---

### 2.4 前端配置界面设计

#### 2.4.1 配置页面入口

**位置**：在"项目设置"或"系统设置"菜单下新增"性能配置"入口

**页面布局**：

```
┌─────────────────────────────────────────────────────────────┐
│                    性能配置                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  【LLM模型配置】                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 最大并发模型数：[1] [2] [3]                           │   │
│  │ 内存限制（MB）：[8192]                                │   │
│  │ 优先模型：[Qwen2.5-14B ▼]                             │   │
│  │ 降级模型：[Qwen2.5-7B ▼]                              │   │
│  │ 单次调用超时（秒）：[30]                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  【解析结果处理】                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 结果选择模式：                                         │   │
│  │   ○ 自动选择最优结果（置信度阈值：0.8）               │   │
│  │   ○ 用户手动选择（对比后让用户确认）                  │   │
│  │   ○ 混合模式（高置信度自动，低置信度用户确认）        │   │
│  │                                                       │   │
│  │ 结果展示模式：                                         │   │
│  │   ○ 简洁模式（只显示最终结果）                        │   │
│  │   ○ 详细模式（显示双引擎对比详情）                    │   │
│  │   ○ 会计模式（按会计准则维度展示）                    │   │
│  │                                                       │   │
│  │ [✓] 显示字段来源引擎                                  │   │
│  │ [✓] 显示置信度评分                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  【OCR配置】                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ OCR引擎：[EasyOCR ▼]                                  │   │
│  │ PDF转图片DPI：[200]                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [测试当前配置] [保存配置]                                  │
└─────────────────────────────────────────────────────────────┘
```

#### 2.4.2 解析结果对比界面（当启用"用户手动选择"时）

```
┌─────────────────────────────────────────────────────────────┐
│              文件解析结果对比                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  文件：工资表_2024-01.xlsx                                  │
│  文档类型：工资表                                            │
│                                                             │
│  ┌───────────────────────┬───────────────────────┐         │
│  │      规则引擎结果      │      LLM引擎结果       │         │
│  ├───────────────────────┼───────────────────────┤         │
│  │ 置信度：0.75          │ 置信度：0.92 ★         │         │
│  │                       │                       │         │
│  │ 工资期间：2024-01      │ 工资期间：2024-01      │         │
│  │ 员工数：5              │ 员工数：5              │         │
│  │ 工资总额：35,000       │ 工资总额：35,000       │         │
│  │                       │                       │         │
│  │ [缺失] 个税计算        │ 个税合计：2,580       │         │
│  │ [缺失] 社保明细        │ 社保合计：3,500       │         │
│  │                       │                       │         │
│  │                       │ 会计分录建议：         │         │
│  │                       │ 借：应付职工薪酬-工资  │         │
│  │                       │ 贷：银行存款...        │         │
│  └───────────────────────┴───────────────────────┘         │
│                                                             │
│  请选择使用哪个结果：                                        │
│  [采用规则引擎结果] [采用LLM引擎结果 ★推荐] [人工复核]      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### 2.5 与解析引擎的集成

#### 2.5.1 引擎调度器使用配置

```python
class ParserEngineDispatcher:
    def __init__(self, config: PerformanceConfig):
        self.config = config
    
    async def dispatch(self, file_path: str, document_type: DocumentType) -> ParseResult:
        """
        根据配置决定解析策略
        """
        # 1. 检查并发限制
        if self.current_concurrent >= self.config.llm_max_concurrent_models:
            # 达到并发上限，只使用规则引擎
            return await self.rule_engine.parse(file_path, document_type)
        
        # 2. 检查内存限制
        if self.get_available_memory() < self.config.llm_memory_limit_mb:
            # 内存不足，使用降级模型
            self.llm_engine.set_model(self.config.llm_fallback_model)
        
        # 3. 根据配置决定是否并行
        if self.config.llm_parallel_enabled:
            # 并行解析
            results = await self.parallel_parse(file_path, document_type)
        else:
            # 先规则，后LLM（串行）
            rule_result = await self.rule_engine.parse(file_path, document_type)
            if rule_result.confidence < self.config.parse_confidence_threshold_auto:
                llm_result = await self.llm_engine.parse(file_path, document_type)
                results = [rule_result, llm_result]
            else:
                results = [rule_result]
        
        # 4. 根据配置决定结果选择方式
        if self.config.parse_result_mode == "auto_best":
            return self.select_best_result(results)
        elif self.config.parse_result_mode == "user_choose":
            return self.prepare_for_user_selection(results)
        else:  # hybrid
            best = self.select_best_result(results)
            if best.confidence >= self.config.parse_confidence_threshold_auto:
                return best
            else:
                return self.prepare_for_user_selection(results)
```

---

## 三、架构设计

### 2.1 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 1: 格式识别层                       │
│  识别文件格式（.pdf/.xlsx/.csv/.jpg/.txt/.docx等）            │
│  → 输出：format_type + format_confidence                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Layer 2: 类型判断层                       │
│  格式特征 + 内容关键词 + 用户预选 → 推断 document_type        │
│  → 冲突时：提示用户选择                                       │
│  → 输出：document_type + type_confidence + possible_types   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Layer 3: 解析引擎层                       │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐        │
│  │ 规则引擎    │   │ LLM引擎     │   │ 融合选择    │        │
│  │ (正则+pandas)│   │ (语义理解)  │   │ (置信度对比)│        │
│  └─────────────┘   └─────────────┘   └─────────────┘        │
│         ↓                ↓                ↓                 │
│  ParseResult_A     ParseResult_B     FinalResult            │
│         └──────────────┬─────────────────┘                  │
│                        ↓                                    │
│              选择置信度高的结果                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 格式识别器（FormatRecognizer）

**职责**：识别文件格式，判断是否可处理

```python
class FileFormat:
    """文件格式类型（扩展支持）"""
    
    # PDF 类
    PDF_TEXT = "pdf_text"        # 文字型PDF（可直接提取文本）
    PDF_IMAGE = "pdf_image"      # 图片型PDF（需要OCR）
    OFD = "ofd"                  # OFD格式（电子发票专用格式）
    
    # 结构化数据类
    EXCEL = "excel"              # Excel文件（.xlsx/.xls）
    CSV = "csv"                  # CSV文件
    XML = "xml"                  # XML格式（电子发票标准格式）
    
    # 图片类
    IMAGE = "image"              # 图片文件（jpg/png/bmp/tiff）
    
    # 文档类
    TEXT = "text"                # 纯文本文件（.txt）
    WORD = "word"                # Word文档（.doc/.docx）
    MARKDOWN = "markdown"        # Markdown文件（.md）
    
    # 特殊类
    UNKNOWN = "unknown"          # 无法识别
```

**实现要点**：
- **PDF**：先尝试pdfplumber提取，文本量<50字符判定为图片型
- **OFD**：使用ofdpy库解析（电子发票专用格式，增值税发票标准格式）
- **XML**：使用lxml解析（增值税电子发票的标准格式）
- **图片型PDF**：调用OCR（pytesseract或EasyOCR）
- **Excel/CSV**：读取表头，识别结构化程度

---

#### 2.2.2 类型判断器（DocumentTypeClassifier）

**职责**：根据格式+内容+用户预选，推断文档类型及其细分类型

```python
class DocumentType:
    """文档主类型"""
    
    # 现有类型
    INVOICE = "invoice"                  # 发票
    BANK_STATEMENT = "bank_statement"    # 银行流水
    CONTRACT = "contract"                # 合同协议
    INVENTORY_RECEIPT = "inventory_receipt"  # 入库单
    
    # 新增类型
    SALARY_TABLE = "salary_table"        # 工资表
    EXPENSE_DOCUMENT = "expense_document"  # 费用单据
    RECEIPT = "receipt"                  # 收据凭证
    
    # 特殊类型
    ACCOUNTING_ENTRY = "accounting_entry"  # 会计凭证/序时簿
    GENERAL = "general"                  # 通用文档
    UNKNOWN = "unknown"                  # 无法确认（需要二次分析）
```

```python
class DocumentSubType:
    """文档细分类型（引擎自适应识别）"""
    
    # === 发票细分类型 ===
    INVOICE_SPECIAL = "invoice_special"        # 增值税专用发票
    INVOICE_NORMAL = "invoice_normal"          # 增值税普通发票
    INVOICE_FIXED = "invoice_fixed"            # 定额发票
    INVOICE_ELECTRONIC = "invoice_electronic"  # 电子发票（XML/OFD格式）
    INVOICE_VAT_GENERAL = "invoice_vat_general"  # 增值税通用机打发票
    
    # === 银行流水细分类型 ===
    BANK_TRANSACTION_LIST = "bank_transaction_list"  # 银行流水单（交易明细）
    BANK_STATEMENT = "bank_statement"                # 银行对账单（期末余额）
    BANK_RECEIPT = "bank_receipt"                    # 银行回单（单笔交易凭证）
    BANK_BALANCE_CONFIRM = "bank_balance_confirm"    # 银行余额确认函
    
    # 银行机构识别（不同银行格式不同）
    BANK_ICBC = "bank_icbc"        # 工商银行
    BANK_ABC = "bank_abc"          # 农业银行
    Bank_BOC = "bank_boc"          # 中国银行
    BANK_CCB = "bank_ccb"          # 建设银行
    BANK_CMBC = "bank_cmbc"        # 招商银行
    BANK_OTHER = "bank_other"      # 其他银行
    
    # === 合同细分类型 ===
    CONTRACT_STANDARD = "contract_standard"        # 标准完整合同（正式格式）
    CONTRACT_SIMPLE = "contract_simple"            # 简易合同（打印版）
    CONTRACT_HANDWRITTEN = "contract_handwritten"  # 手写合同
    CONTRACT_TEMPLATE = "contract_template"        # 模板化合同（如报装单、订单确认单）
    CONTRACT_ORDER = "contract_order"              # 订单/报装单（预定格式）
    
    # === 入库单细分类型（广义物流/销售单据）===
    INVENTORY_STANDARD = "inventory_standard"          # 标准入库单
    LOGISTICS_RECEIPT = "logistics_receipt"            # 物流签收单
    SALES_ORDER = "sales_order"                        # 销售订单
    PURCHASE_ORDER = "purchase_order"                  # 采购订单
    DELIVERY_NOTE = "delivery_note"                    # 送货单
    
    # 电商平台单据
    ECOM_ORDER = "ecom_order"            # 电商平台订单
    ECOM_BILL = "ecom_bill"              # 电商平台账单
    ECOM_SETTLEMENT = "ecom_settlement"  # 电商平台结算单
    
    # === 工资表细分类型 ===
    SALARY_STANDARD = "salary_standard"        # 标准工资表
    SALARY_SIMPLE = "salary_simple"            # 简易工资表
    SALARY_COMMISSION = "salary_commission"    # 提成计算表
    SALARY_DETAILED = "salary_detailed"        # 详细工资明细表
    
    # === 费用单据细分类型（最广义）===
    EXPENSE_TRAVEL = "expense_travel"            # 差旅报销单
    EXPENSE_ENTERTAINMENT = "expense_entertainment"  # 业务招待单
    EXPENSE_OFFICE = "expense_office"            # 办公费用报销单
    EXPENSE_TRANSPORT = "expense_transport"      # 交通费用单
    EXPENSE_TRAIN = "expense_train"              # 培训费用单
    EXPENSE_OTHER = "expense_other"              # 其他费用单据
    
    # 行程类单据
    ITINERARY_FLIGHT = "itinerary_flight"    # 航班行程单
    ITINERARY_TRAIN = "itinerary_train"      # 铁路行程单
    ITINERARY_HOTEL = "itinerary_hotel"      # 酒店订单
    ITINERARY_OTHER = "itinerary_other"      # 其他行程单据
    
    # === 收据细分类型 ===
    RECEIPT_PRINTED = "receipt_printed"      # 印刷收据（标准格式）
    RECEIPT_HANDWRITTEN = "receipt_handwritten"  # 手写收据
    RECEIPT_INVOICE = "receipt_invoice"      # 收据型发票（税务监制）
    RECEIPT_INTERNAL = "receipt_internal"    # 内部收据
    
    # === 未识别类型 ===
    UNKNOWN_PENDING = "unknown_pending"      # 待二次分析
    UNKNOWN_UNSUPPORTED = "unknown_unsupported"  # 不支持的格式
```

**判断逻辑**：
1. **用户预选优先**：上传时用户选择类型 → 直接使用，跳过判断
2. **格式特征**：根据文件格式推断候选类型集
   - Excel → [银行流水, 工资表, 费用单据, 入库单, 会计凭证]
   - PDF → [发票, 合同, 收据]
   - 图片 → [发票, 收据]
   - XML/OFD → [电子发票]
3. **内容关键词**：提取文本，匹配关键词缩小范围
4. **细分类型识别**：在确定主类型后，进一步识别细分类型
   - 发票：识别发票类型（专用/普通/定额/电子）
   - 银行流水：识别银行机构和单据类型（流水单/对账单/回单）
   - 合同：识别合同形式（标准/简易/手写/模板）
   - 入库单：识别单据性质（入库/物流/销售/电商）
5. **冲突处理**：格式推断与内容特征不一致 → 返回候选列表，前端让用户确认

---

#### 2.2.2.1 未识别文件处理流程

**设计目标**：对于无法立即识别的文件，定义存储对象和二次分析流程

```python
@dataclass
class UnrecognizedFile:
    """未识别文件对象"""
    
    # 基本信息
    file_id: int                          # 文件ID
    file_path: str                        # 文件存储路径
    file_name: str                        # 文件名
    file_format: FileFormat               # 文件格式（已知）
    upload_time: datetime                 # 上传时间
    
    # 分析状态
    analysis_status: str                  # 分析状态
    # - "pending": 待分析（首次未能识别）
    # - "analyzing": 正在二次分析
    # - "identified": 已识别（二次分析成功）
    # - "failed": 识别失败（需人工介入）
    
    # 初次分析结果
    first_analysis: dict[str, Any]        # 初次分析结果
    # 包含：尝试的类型列表、各类型置信度、拒绝原因
    
    # 二次分析结果
    second_analysis: dict[str, Any]       # 二次分析结果（可选）
    # 包含：最终识别的类型、细分类型、置信度
    
    # 提取的内容
    extracted_text: str                   # 提取的文本内容
    extracted_features: dict[str, Any]    # 提取的特征（关键词、金额、日期等）
    
    # 用户反馈
    user_manual_type: DocumentType        # 用户手动指定的类型（可选）
    user_manual_sub_type: DocumentSubType # 用户手动指定的细分类型（可选）
```

**二次分析流程**：

```python
async def analyze_unrecognized_file(file: UnrecognizedFile) -> AnalysisResult:
    """
    未识别文件的二次分析流程
    
    流程：
    1. 遍历所有已知文档类型，尝试识别
    2. 对每种类型进行细分类型检测
    3. 记录各类型的匹配得分
    4. 选择得分最高的类型（或请求用户确认）
    """
    
    results = []
    
    # 1. 遍历所有主类型
    for doc_type in DocumentType.get_all_types():
        # 跳过已知不可处理的类型
        if doc_type == DocumentType.UNKNOWN:
            continue
        
        # 2. 尝试识别该类型
        type_result = await try_identify_type(file, doc_type)
        results.append(type_result)
    
    # 3. 对高置信度的类型，尝试细分类型识别
    for result in results:
        if result.confidence > 0.5:
            sub_type = await try_identify_sub_type(file, result.document_type)
            result.sub_type = sub_type
    
    # 4. 选择最佳结果
    best_result = max(results, key=lambda r: r.confidence)
    
    if best_result.confidence >= 0.6:
        # 成功识别
        file.analysis_status = "identified"
        file.second_analysis = best_result.to_dict()
        return best_result
    else:
        # 需要用户介入
        file.analysis_status = "failed"
        file.first_analysis["all_attempts"] = results
        # 返回候选列表，让用户选择
        return AnalysisResult(
            status="need_user_input",
            candidates=results[:3],  # 返回前3个候选
            message="系统无法确定文件类型，请手动选择或提供更多信息"
        )
```

**二次分析触发条件**：

| 条件 | 触发时机 |
|------|---------|
| 初次识别置信度 < 0.4 | 立即进入二次分析队列 |
| 用户请求重新分析 | 手动触发二次分析 |
| 批量处理完成后 | 对所有未识别文件统一分析 |
| 有新模板/规则更新 | 对未识别文件重新匹配 |

---

#### 2.2.2.2 细分类型识别策略

**发票细分类型识别**：

```python
def identify_invoice_sub_type(text: str, file_format: FileFormat) -> DocumentSubType:
    """
    发票细分类型识别策略
    
    识别依据：
    1. 文件格式：XML/OFD → 电子发票
    2. 发票代码：专用发票代码范围 vs 普通发票代码范围
    3. 发票内容关键词：定额发票特征、机打发票特征
    """
    
    # 1. 格式优先判断
    if file_format == FileFormat.XML or file_format == FileFormat.OFD:
        return DocumentSubType.INVOICE_ELECTRONIC
    
    # 2. 发票代码判断（发票代码前缀区分类型）
    invoice_code_match = re.search(r"发票代码[：:]\s*(\d+)", text)
    if invoice_code_match:
        code = invoice_code_match.group(1)
        # 专用发票代码通常以特定数字开头
        if code.startswith(("3100", "3200", "1100")):
            return DocumentSubType.INVOICE_SPECIAL
        elif code.startswith(("1300", "1400")):
            return DocumentSubType.INVOICE_NORMAL
    
    # 3. 关键词判断
    if "定额发票" in text or "有奖发票" in text:
        return DocumentSubType.INVOICE_FIXED
    
    if "机打发票" in text or "通用机打" in text:
        return DocumentSubType.INVOICE_VAT_GENERAL
    
    # 4. 默认返回普通发票
    return DocumentSubType.INVOICE_NORMAL
```

**银行流水细分类型识别**：

```python
def identify_bank_sub_type(text: str, headers: list[str]) -> DocumentSubType:
    """
    银行流水细分类型识别策略
    
    识别依据：
    1. 银行名称关键词：识别具体银行
    2. 表头特征：流水单（交易明细） vs 对账单（期初/期末余额） vs 回单（单笔）
    3. 文件名特征：包含"流水"、"对账单"、"回单"等关键词
    """
    
    # 1. 银行机构识别
    bank_keywords = {
        "工商银行": DocumentSubType.BANK_ICBC,
        "农业银行": DocumentSubType.BANK_ABC,
        "中国银行": DocumentSubType.BANK_BOC,
        "建设银行": DocumentSubType.BANK_CCB,
        "招商银行": DocumentSubType.BANK_CMBC,
    }
    
    for keyword, sub_type in bank_keywords.items():
        if keyword in text:
            bank_type = sub_type
            break
    else:
        bank_type = DocumentSubType.BANK_OTHER
    
    # 2. 单据类型识别
    # 流水单特征：包含"交易明细"、"交易日期"、"对方账户"
    if any(kw in " ".join(headers).lower() for kw in ["交易明细", "transaction", "对方账户"]):
        return DocumentSubType.BANK_TRANSACTION_LIST
    
    # 对账单特征：包含"期初余额"、"期末余额"
    if any(kw in text for kw in ["期初余额", "期末余额", "期初", "期末"]):
        return DocumentSubType.BANK_STATEMENT
    
    # 回单特征：单笔交易、包含"回单编号"
    if "回单" in text or "凭证号" in text:
        return DocumentSubType.BANK_RECEIPT
    
    # 余额确认函特征
    if "余额确认" in text or "函" in text:
        return DocumentSubType.BANK_BALANCE_CONFIRM
    
    # 默认返回流水单
    return DocumentSubType.BANK_TRANSACTION_LIST
```

**合同细分类型识别**：

```python
def identify_contract_sub_type(text: str, file_format: FileFormat) -> DocumentSubType:
    """
    合同细分类型识别策略
    
    识别依据：
    1. 合同完整性：是否包含"合同"字样及完整条款
    2. 格式特征：是否为模板化格式（如报装单、订单确认单）
    3. 内容特征：手写痕迹（OCR识别的特殊字符）
    """
    
    # 1. 模板化合同判断（预定格式的订单/报装单）
    template_keywords = ["报装单", "订单确认", "订单号", "订购单", "申请单"]
    if any(kw in text for kw in template_keywords):
        return DocumentSubType.CONTRACT_ORDER
    
    # 2. 标准完整合同判断
    standard_keywords = ["合同编号", "甲方", "乙方", "签订日期", "合同金额", "违约责任"]
    matched = sum(1 for kw in standard_keywords if kw in text)
    if matched >= 4:
        return DocumentSubType.CONTRACT_STANDARD
    
    # 3. 简易合同判断
    if matched >= 2:
        return DocumentSubType.CONTRACT_SIMPLE
    
    # 4. 手写合同判断（OCR特征：不规则字符、笔画痕迹）
    if file_format == FileFormat.PDF_IMAGE or file_format == FileFormat.IMAGE:
        # 通过OCR结果特征判断（需要特殊处理）
        # 例如：检测手写笔迹特征
        pass
    
    # 5. 默认返回标准合同
    return DocumentSubType.CONTRACT_TEMPLATE
```

**入库单细分类型识别（广义物流/销售单据）**：

```python
def identify_inventory_sub_type(text: str, headers: list[str]) -> DocumentSubType:
    """
    入库单细分类型识别策略（广义物流/销售单据）
    
    识别依据：
    1. 单据性质：入库单 vs 物流单 vs 销售单 vs 电商订单
    2. 来源特征：电商平台关键词（淘宝、京东等）
    3. 表头特征：入库单特征 vs 销售单特征
    """
    
    # 1. 电商平台单据判断
    ecom_keywords = ["淘宝", "天猫", "京东", "拼多多", "抖音", "美团", "饿了么"]
    for kw in ecom_keywords:
        if kw in text:
            # 进一步区分订单、账单、结算单
            if "订单" in text:
                return DocumentSubType.ECOM_ORDER
            elif "账单" in text or "结算" in text:
                return DocumentSubType.ECOM_SETTLEMENT
            else:
                return DocumentSubType.ECOM_BILL
    
    # 2. 物流单判断
    logistics_keywords = ["物流", "快递", "签收", "运单", "快递单号"]
    if any(kw in text for kw in logistics_keywords):
        return DocumentSubType.LOGISTICS_RECEIPT
    
    # 3. 销售单判断
    sales_keywords = ["销售", "出货", "客户", "订单"]
    if any(kw in text for kw in sales_keywords):
        return DocumentSubType.SALES_ORDER
    
    # 4. 采购单判断
    purchase_keywords = ["采购", "供应商", "进货"]
    if any(kw in text for kw in purchase_keywords):
        return DocumentSubType.PURCHASE_ORDER
    
    # 5. 送货单判断
    delivery_keywords = ["送货", "发货", "配送"]
    if any(kw in text for kw in delivery_keywords):
        return DocumentSubType.DELIVERY_NOTE
    
    # 6. 标准入库单判断
    inventory_keywords = ["入库", "收货", "验收"]
    if any(kw in text for kw in inventory_keywords):
        return DocumentSubType.INVENTORY_STANDARD
    
    # 7. 默认返回标准入库单
    return DocumentSubType.INVENTORY_STANDARD
```

**费用单据细分类型识别（最广义）**：

```python
def identify_expense_sub_type(text: str) -> DocumentSubType:
    """
    费用单据细分类型识别策略（最广义）
    
    识别依据：
    1. 费用类型关键词：差旅、招待、办公、交通等
    2. 行程类单据：航班、铁路、酒店等
    3. 特殊格式特征
    """
    
    # 1. 行程类单据判断（优先判断）
    if "航班" in text or "机票" in text or "航空" in text:
        return DocumentSubType.ITINERARY_FLIGHT
    
    if "火车" in text or "铁路" in text or "车票" in text:
        return DocumentSubType.ITINERARY_TRAIN
    
    if "酒店" in text or "住宿" in text:
        return DocumentSubType.ITINERARY_HOTEL
    
    # 2. 差旅报销单判断
    if "差旅" in text or "出差" in text:
        return DocumentSubType.EXPENSE_TRAVEL
    
    # 3. 业务招待判断
    if "招待" in text or "宴请" in text:
        return DocumentSubType.EXPENSE_ENTERTAINMENT
    
    # 4. 办公费用判断
    if "办公" in text or "办公用品" in text:
        return DocumentSubType.EXPENSE_OFFICE
    
    # 5. 交通费用判断
    if "交通" in text or "打车" in text or "出租" in text:
        return DocumentSubType.EXPENSE_TRANSPORT
    
    # 6. 培训费用判断
    if "培训" in text or "会议" in text:
        return DocumentSubType.EXPENSE_TRAIN
    
    # 7. 其他费用单据
    return DocumentSubType.EXPENSE_OTHER
```

#### 2.2.3 解析引擎调度器（ParserEngineDispatcher）

**职责**：调度规则引擎和LLM引擎并行解析，融合选择最优结果

**双引擎并行机制**：

```python
@dataclass
class ParseResult:
    document_type: DocumentType
    data: dict[str, Any]          # 解析结果数据
    confidence: float             # 置信度 0-1
    engine: str                   # 来源引擎：rule/llm/fused
    raw_text: str                 # 原始文本
    validation_errors: list[str]  # 校验错误
    accounting_notes: str         # 会计处理说明
```

**调度流程**：
1. 同时启动规则解析和LLM解析（异步并行）
2. 规则引擎返回：ParseResult_rule（置信度、字段、错误）
3. LLM引擎返回：ParseResult_llm（置信度、字段、会计说明）
4. 融合选择：
   - 若 rule.confidence >= 0.8 且无校验错误 → 采用规则结果（更快）
   - 若 llm.confidence > rule.confidence → 采用LLM结果（更准）
   - 若两者都有校验错误 → 返回错误提示，请求用户复核
   - 若置信度相近 → 合并两者结果，标注字段来源

#### 2.2.4 深度解析模板（AccountingStandardTemplate）

**职责**：为每种文档类型定义准则级别的解析模板

| 文档类型 | 会计准则/依据 | 深度解析需求 |
|---------|--------------|------------|
| **发票** | 增值税会计处理规定 | 价税分离、进项/销项、税率匹配、发票认证状态 |
| **银行流水** | 现金流量表编制 | 收付性质分类、现金流量项目、银行 reconciliation |
| **合同** | CAS 14 收入准则 | 五步法模型（已实现） |
| **入库单** | 存货核算（CAS 1） | 存货成本、入库时间、供应商往来 |
| **工资表** | 薪酬核算、个人所得税 | 工资明细、社保公积金、个税计算、应付职工薪酬 |
| **费用单据** | 费用核算、报销管理 | 费用类型、报销人、审批、费用分摊、期间归属 |
| **收据** | 内部凭证管理 | 收款方、付款方、金额、用途、凭证编号 |
| **会计凭证** | 凭证编制规范 | 借贷平衡、科目合规、摘要规范、附件勾稽 |

---

## 三、新增文档类型详细设计

### 3.1 工资表（SalaryTable）

**会计准则依据**：
- 《企业会计准则第9号——职工薪酬》
- 《个人所得税法》及相关规定

**深度解析字段**：

```python
@dataclass
class SalaryParseResult:
    # 基本信息
    period: str                    # 工资期间（2024-01）
    company_name: str              # 发放单位
    
    # 员工明细列表
    employees: list[EmployeeSalary]
    
    # 合计数据
    total_gross_salary: Decimal    # 工资总额
    total_social_insurance: Decimal  # 社保合计
    total_housing_fund: Decimal    # 公积金合计
    total_income_tax: Decimal      # 个税合计
    total_net_salary: Decimal      # 实发合计
    
    # 会计处理说明
    accounting_entries: list[dict]  # 建议会计分录
    # 例如：借：应付职工薪酬-工资 / 贷：银行存款、应交税费-个人所得税
    
    # 置信度
    confidence: float
```

**EmployeeSalary 结构**：

```python
@dataclass
class EmployeeSalary:
    name: str                      # 员工姓名
    department: str                # 部门
    position: str                  # 职位
    base_salary: Decimal           # 基本工资
    bonus: Decimal                 # 奖金
    allowance: Decimal             # 补贴
    overtime_pay: Decimal          # 加班费
    gross_salary: Decimal          # 应发合计
    
    # 扣除项
    social_insurance_personal: Decimal  # 个人社保
    social_insurance_company: Decimal   # 公司社保
    housing_fund_personal: Decimal      # 个人公积金
    housing_fund_company: Decimal       # 公司公积金
    income_tax: Decimal                 # 个人所得税
    other_deduction: Decimal            # 其他扣款
    
    net_salary: Decimal            # 实发金额
    bank_account: str              # 银行账号
```

### 3.2 费用单据（ExpenseDocument）

**会计准则依据**：
- 费用核算规范
- 差旅费、招待费等专项规定

**深度解析字段**：

```python
@dataclass
class ExpenseParseResult:
    # 基本信息
    document_number: str           # 单据编号
    expense_date: date             # 费用发生日期
    submitter: str                 # 报销人
    department: str                # 所属部门
    
    # 费用明细
    expense_type: str              # 费用类型（差旅/招待/办公/交通等）
    expense_items: list[ExpenseItem]
    
    # 金额数据
    total_amount: Decimal          # 总金额
    tax_amount: Decimal            # 税额（如有）
    
    # 审批信息
    approver: str                  # 审批人
    approval_date: date            # 审批日期
    approval_status: str           # 审批状态
    
    # 分摊信息
    cost_center: str               # 成本中心/项目
    allocation_ratio: float        # 分摊比例
    
    # 会计处理
    accounting_entry: dict         # 建议分录
    # 例如：借：管理费用-差旅费 / 贷：其他应收款-XX
    
    # 关联凭证
    related_invoice: str           # 关联发票号
    related_voucher: str           # 关联凭证号
```

### 3.3 收据凭证（Receipt）

**会计准则依据**：
- 内部凭证管理规范
- 收付款核算规范

**深度解析字段**：

```python
@dataclass
class ReceiptParseResult:
    # 基本信息
    receipt_number: str            # 收据编号
    receipt_date: date            # 收据日期
    receipt_type: str             # 收据类型（收款/付款）
    
    # 当事人
    payer: str                    # 付款方
    payer_account: str            # 付款方账号
    receiver: str                 # 收款方
    receiver_account: str         # 收款方账号
    
    # 金额数据
    amount: Decimal               # 金额
    purpose: str                  # 用途/摘要
    payment_method: str           # 支付方式（现金/转账/支票）
    
    # 关联信息
    related_contract: str         # 关联合同
    related_invoice: str          # 关联发票
    
    # 会计处理
    accounting_entry: dict        # 建议分录
```

---

## 四、解析引擎分工

### 4.1 规则引擎（RuleEngine）

**适用场景**：
- 结构化表格（Excel/CSV）：银行流水、工资表、会计凭证
- 固定格式文档：发票（税务标准格式）、入库单

**技术栈**：
- pandas：表格解析、表头映射
- 正则表达式：关键词提取、模式匹配
- 表头自适应模板：`format_template.py`（已实现）

**优势**：
- 速度快（毫秒级）
- 结果稳定、可复现
- 不依赖外部服务

**局限**：
- 非标准格式处理能力弱
- 无法理解语义（如履约义务、费用分摊）
- 无法生成会计处理建议

### 4.2 LLM引擎（LLMEngine）

**适用场景**：
- 非结构化文本：合同协议、费用单据说明
- 图片型文档：图片型发票、收据
- 语义理解需求：履约义务识别、费用分摊判断、会计分录建议

**技术栈**：
- 本地模型：Qwen2.5-14B-Instruct（INT4量化，约8-9GB内存）
- API调用：`llm_client_service.py`（支持Ollama）
- Prompt模板：每种文档类型设计专用Prompt

**优势**：
- 语义理解能力强
- 可生成会计处理建议
- 适应非标准格式

**局限**：
- 速度慢（秒级）
- 结果可能有幻觉（需要校验）
- 依赖模型配置

### 4.3 双引擎协作机制

```python
async def parse_document(file_path: str, document_type: DocumentType) -> ParseResult:
    """
    双引擎并行解析
    """
    # 1. 提取原始文本
    raw_text = extract_text(file_path)
    
    # 2. 并行启动两个引擎
    rule_future = asyncio.create_task(
        rule_engine.parse(file_path, document_type, raw_text)
    )
    llm_future = asyncio.create_task(
        llm_engine.parse(file_path, document_type, raw_text)
    )
    
    # 3. 等待结果
    rule_result = await rule_future
    llm_result = await llm_future
    
    # 4. 融合选择
    if rule_result.confidence >= 0.8 and not rule_result.validation_errors:
        return rule_result
    elif llm_result.confidence > rule_result.confidence:
        return llm_result
    else:
        # 合并结果，标注字段来源
        return fuse_results(rule_result, llm_result)
```

---

## 五、实施计划

### Phase 1：基础架构重构（预计工作量：中等）

**目标**：建立三层架构框架

**任务清单**：
1. 创建 `format_recognizer.py` - 格式识别层
2. 创建 `document_type_classifier.py` - 类型判断层（含冲突处理）
3. 创建 `parser_engine_dispatcher.py` - 引擎调度层
4. 创建 `parse_result.py` - 统一结果数据结构
5. 重构 `import_service.py` - 集成新架构

**验证标准**：
- 能正确识别文件格式（PDF文字型/图片型、Excel、CSV、图片等）
- 能根据格式+内容推断文档类型，冲突时返回候选列表
- 双引擎能并行启动并返回结果

### Phase 2：新增文档类型解析（预计工作量：较高）

**目标**：实现工资表、费用单据、收据的深度解析

**任务清单**：
1. 创建 `salary_parser_service.py` - 工资表解析服务
   - 规则解析：pandas读取表格 + 表头映射
   - LLM解析：Prompt提取员工明细 + 会计分录建议
   - 会计校验：应付职工薪酬勾稽
   
2. 创建 `expense_parser_service.py` - 费用单据解析服务
   - 规则解析：表格结构识别
   - LLM解析：费用类型分类 + 分摊判断
   - 会计校验：费用科目匹配
   
3. 创建 `receipt_parser_service.py` - 收据解析服务
   - 规则解析：编号、金额、日期提取
   - LLM解析：用途理解 + 关联信息
   - 会计校验：收付性质判断
   
4. 创建LLM Prompt模板库
   - `salary_prompt.py`
   - `expense_prompt.py`
   - `receipt_prompt.py`

**验证标准**：
- 工资表能提取员工明细、社保公积金、个税计算
- 费用单据能识别费用类型、报销人、审批信息
- 收据能提取编号、金额、当事人、用途
- 三种类型都能生成会计处理建议

### Phase 3：现有类型深度解析增强（预计工作量：中等）

**目标**：为发票、银行流水、入库单增加准则级别深度解析

**任务清单**：
1. 增强 `invoice_parser_service.py`
   - 新增增值税会计处理：价税分离、进项/销项判断
   - 新增发票认证状态识别
   - 新增会计分录建议
   
2. 增强 `bank_statement_parser_service.py`
   - 新增现金流量项目分类
   - 新增银行 reconciliation 提示
   - 新增会计分录建议
   
3. 增强 `inventory_receipt_parser_service.py`
   - 新增存货成本核算（CAS 1）
   - 新增供应商往来匹配
   - 新增会计分录建议

**验证标准**：
- 发票解析能区分进项/销项、计算税额、建议分录
- 银行流水能按现金流量分类、提示 reconciliation
- 入库单能计算存货成本、匹配供应商

### Phase 4：前端集成与用户确认机制（预计工作量：中等）

**目标**：前端展示解析结果，支持冲突确认和人工复核

**任务清单**：
1. 修改上传页面：增加文件类型预选选项
2. 修改草稿页面：展示解析结果详情（按会计准则维度）
3. 增加冲突确认弹窗：格式+内容冲突时让用户选择
4. 增加人工复核入口：置信度低或校验错误时请求复核

**验证标准**：
- 用户可预选文件类型
- 解析结果展示完整（包含会计处理建议）
- 冲突时弹窗让用户确认
- 低置信度时提示复核

---

## 六、关键技术选型

### 6.1 OCR引擎

**当前**：EasyOCR + pytesseract

**建议**：保持现有方案，增加PaddleOCR备选

| OCR引擎 | 优点 | 缺点 | 适用场景 |
|--------|------|------|---------|
| EasyOCR | 支持多语言、安装简单 | 速度较慢 | 一般图片 |
| pytesseract | 配合pdf2image处理PDF | 中文效果一般 | 图片型PDF |
| PaddleOCR | 中文效果好、免费 | 安装复杂 | 中文发票/收据 |

### 6.2 LLM模型

**推荐**：Qwen2.5-14B-Instruct（INT4量化）

- 内存占用：约8-9GB（M1 32GB可流畅运行）
- 中文能力：优秀（财务专业词汇理解强）
- 结构化输出：支持JSON格式
- 成本：本地免费运行

### 6.3 表格解析

**当前**：pandas + 自适应模板

**保持现有方案**，增加LLM辅助表头理解

---

## 七、边界与假设

### 7.1 本次规划范围（In Scope）

- 文件解析引擎架构重构
- 新增文档类型（工资表、费用单据、收据）的深度解析
- 现有类型（发票、银行流水、入库单）的深度解析增强
- 双引擎并行+置信度选择机制
- 格式+内容双验证+冲突用户确认
- 前端解析结果展示和人工复核入口

### 7.2 本次规划不涉及（Out of Scope）

- 审计模块改动（审计证据、审计任务）
- 凭证生成模块改动（Step3 AI生成凭证）
- 报表模块改动（资产负债表、利润表）
- 导航/菜单调整
- 用户权限改动
- 数据库结构大规模改动（仅新增解析结果字段）

### 7.3 假设与前提

- 用户本地已部署Ollama并配置Qwen2.5-14B模型
- 用户接受解析速度较慢（单份文档10-30秒）
- 用户愿意在上传时预选文件类型或确认冲突
- 用户有会计专业知识，能复核解析结果

---

## 八、验证计划

### 8.1 单元测试

- 格式识别器：各类文件格式识别准确率 >95%
- 类型判断器：已知文档类型推断准确率 >90%
- 解析引擎：每种类型至少3个真实样本解析成功

### 8.2 集成测试

- 上传 → 格式识别 → 类型判断 → 双引擎解析 → 结果展示完整流程
- 冲突场景：格式与内容不一致时返回候选列表
- 低置信度场景：置信度<0.6时提示复核

### 8.3 业务验证

- 工资表：与手工核算的工资明细对比，金额误差<0.01元
- 费用单据：费用类型分类准确率>85%
- 收据：关键字段提取完整率>90%
- 发票：价税分离准确率>95%
- 银行流水：现金流量分类准确率>80%

---

## 九、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| LLM幻觉 | 解析结果有错误字段 | 增加校验层，对比勾稽关系 |
| OCR效果差 | 图片型PDF提取失败 | 增加PaddleOCR备选，提示用户转格式 |
| 内存不足 | 本地模型无法运行 | 提供降级方案（Qwen2.5-7B或API） |
| 冲突频繁 | 用户体验差 | 增加预选类型入口，减少判断依赖 |
| 解析超时 | 前端等待过长 | 增加进度提示，允许后台处理 |

---

## 十、依赖关系

**前置依赖**：
- 本地Ollama配置完成
- Qwen2.5-14B模型拉取完成
- 现有解析服务可用（测试通过）

**后续任务**：
- 凭证生成模块可调用解析结果
- 报表模块可引用台账数据
- 审计模块可引用原始资料解析结果

---

## 附录：文件目录结构规划

```
backend/app/services/
├── parser_engine/                    # 新增：解析引擎模块
│   ├── __init__.py
│   ├── format_recognizer.py          # 格式识别层
│   ├── document_type_classifier.py   # 类型判断层
│   ├── parser_engine_dispatcher.py   # 引擎调度层
│   ├── parse_result.py               # 统一结果结构
│   ├── rule_engine.py                # 规则引擎基类
│   ├── llm_engine.py                 # LLM引擎基类
│   ├── result_fuser.py               # 结果融合器
│   └── prompts/                      # LLM Prompt模板
│       ├── salary_prompt.py
│       ├── expense_prompt.py
│       ├── receipt_prompt.py
│       ├── invoice_prompt.py
│       ├── bank_statement_prompt.py
│       └── inventory_prompt.py
│
├── parsers/                          # 新增：各类型解析器
│   ├── __init__.py
│   ├── salary_parser_service.py      # 工资表解析
│   ├── expense_parser_service.py     # 费用单据解析
│   ├── receipt_parser_service.py     # 收据解析
│   ├── invoice_parser_enhanced.py    # 发票增强解析
│   ├── bank_statement_enhanced.py    # 银行流水增强
│   └── inventory_enhanced.py         # 入库单增强
│
├── source_document_service.py        # 保留：原始资料服务（重构调度逻辑）
├── contract_parser_service.py        # 保留：合同解析（CAS 14）
├── file_parser_service.py            # 保留：会计凭证解析
├── ocr_service.py                    # 保留：OCR服务
├── llm_client_service.py             # 保留：LLM客户端
└── import_service.py                 # 重构：集成新架构
```

---

**规划完成时间**：2026-06-26
**规划版本**：v1.0
**下一步**：用户确认后开始实施Phase 1