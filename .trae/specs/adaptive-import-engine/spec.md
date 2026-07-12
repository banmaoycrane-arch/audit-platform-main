# 自适应文件导入引擎（场景 A：电子档案 / 结构化导入）

```text
Domain: D05 - 原始资料导入与解析
Status: active-main
Owner Spec: adaptive-import-engine（本文档）
Depends On: document-parsing-engine（双场景总纲）, parser-dual-scenario-strategy.md
In Scope:
- Excel/CSV 序时账、凭证表、网银导出
- 表头检测、模板匹配、字段别名、质量分
- file_parser_service.parse_entries 路径
Out of Scope:
- PDF/扫描合同分层（场景 B → document-parsing-engine + seal）
- 印章识别、合同深度语义
- 正式凭证 post
Acceptance Level: TOP3 样本集字段准确率 ≥95%（序时簿）/ ≥90%（结构化流水）
```

> 双场景总纲见 [parser-dual-scenario-strategy.md](../../documents/parser-dual-scenario-strategy.md)。

## 1. 问题分析

### 1.1 当前问题
- 字段映射是**硬编码**的（`file_parser_service.py` 的 `_pick` 函数）
- 只支持固定的中英文字段名列表
- 不支持动态适配不同格式的 Excel/CSV 文件
- 凭证和原始文件处理逻辑混合

### 1.2 用户期望
- **会计凭证**：建立格式模板 + AI 智能字段识别
- **原始文件**：标准化解析 + AI 辅助分类
- **核心原则**：自适应引擎 + 最小人工干预 + 固定流程前置

## 2. 架构设计

### 2.1 自适应导入引擎架构

```
┌─────────────────────────────────────────────────────────────┐
│                    自适应导入引擎                              │
├─────────────────────────────────────────────────────────────┤
│  1. 格式检测层                                              │
│     - 文件类型识别（Excel/CSV/PDF/图片）                     │
│     - 表头行检测                                             │
│     - 数据行范围识别                                          │
├─────────────────────────────────────────────────────────────┤
│  2. 字段映射层                                              │
│     - 模板匹配（预定义格式模板）                              │
│     - AI 智能映射（未知格式时调用大模型）                      │
│     - 映射结果缓存                                            │
├─────────────────────────────────────────────────────────────┤
│  3. 数据标准化层                                             │
│     - 字段类型转换（日期/金额/文本）                          │
│     - 数据清洗（空值/异常值处理）                            │
│     - 标准化输出                                              │
├─────────────────────────────────────────────────────────────┤
│  4. 验证层                                                  │
│     - 必填字段检查                                            │
│     - 数据质量评分                                            │
│     - 异常预警                                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 会计凭证 vs 原始文件 分离处理

| 维度 | 会计凭证 | 原始文件 |
|-----|---------|---------|
| 目标 | 解析结构化分录 | 抽取文本内容 |
| 输入 | Excel/CSV | PDF/TXT/图片 |
| 模板 | 财务科目体系 | 文档分类模板 |
| AI 干预 | 字段映射辅助 | 内容分类/摘要 |
| 输出 | AccountingEntry | SourceFile + extracted_text |

## 3. 实现计划

### Phase 1: 模板系统（固定流程前置）
1. 创建预定义格式模板库
2. 实现模板匹配引擎
3. 支持字段别名映射表

### Phase 2: 自适应引擎
1. 实现表头智能识别
2. 字段类型自动推断
3. 映射失败时的 AI 辅助

### Phase 3: 质量保障
1. 数据质量评分
2. 导入报告生成
3. 异常检测与预警

## 4. 核心文件变更

| 文件 | 变更内容 |
|-----|---------|
| `file_parser_service.py` | 重构为模块化解析器 |
| `import_service.py` | 分离凭证/文件处理流程 |
| 新增 `format_template.py` | 格式模板管理 |
| 新增 `adaptive_mapper.py` | 自适应字段映射 |
| 新增 `data_validator.py` | 数据验证与质量评分 |

## 5. 模板格式示例

```python
# 会计凭证模板
ACCOUNTING_TEMPLATES = {
    "标准中文": {
        "fields": {
            "voucher_no": ["凭证号", "凭证编号", "编号"],
            "voucher_date": ["凭证日期", "日期", "记账日期"],
            "summary": ["摘要", "说明", "描述"],
            "account_code": ["科目编码", "科目代码"],
            "account_name": ["科目名称", "会计科目", "科目"],
            "debit_amount": ["借方金额", "借方", " debit"],
            "credit_amount": ["贷方金额", "贷方", "credit"],
            "counterparty": ["往来单位", "供应商", "客户", "对方单位"],
        },
        "required": ["summary", "account_name", ("debit_amount", "credit_amount")],
    },
    "标准英文": {
        "fields": {
            "voucher_no": ["voucher_no", "voucher", "凭证号"],
            "voucher_date": ["voucher_date", "date", "日期"],
            "summary": ["summary", "description", "摘要"],
            "account_code": ["account_code", "account_id"],
            "account_name": ["account_name", "account", "account_title"],
            "debit_amount": ["debit_amount", "debit", "借方金额"],
            "credit_amount": ["credit_amount", "credit", "贷方金额"],
            "counterparty": ["counterparty", "supplier", "customer"],
        },
        "required": ["summary", "account_name", ("debit_amount", "credit_amount")],
    },
}
```

## 6. AI 辅助映射（可选）

当模板匹配失败时，调用 AI 分析表头并生成映射：

```python
def ai_assist_mapping(headers: list[str]) -> dict[str, str]:
    """调用 AI 分析表头，生成字段映射"""
    prompt = f"""
    以下是 Excel/CSV 文件的表头：
    {headers}
    
    请识别每个表头对应的标准会计分录字段：
    - voucher_no: 凭证号
    - voucher_date: 凭证日期
    - summary: 摘要
    - account_code: 科目编码
    - account_name: 科目名称
    - debit_amount: 借方金额
    - credit_amount: 贷方金额
    - counterparty: 往来单位
    
    返回 JSON 格式的映射关系。
    """
    # 调用 AI 服务...
```
