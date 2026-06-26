# -*- coding: utf-8 -*-
"""
文件解析引擎模块

统一入口，提供便捷的解析函数

模块功能：文件解析引擎统一入口
业务场景：支持多种财务文档的深度解析，提供准则级别的会计处理建议
政策依据：各类会计准则（CAS 1/9/14/22等）
创建日期：2026-06-26
更新记录：
    2026-06-26  初始创建，导出所有模块功能
"""

# 导入数据结构
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
    DOCUMENT_TYPE_LABELS,
    DOCUMENT_SUB_TYPE_LABELS,
    FILE_FORMAT_LABELS,
)

# 导入格式识别层
from app.services.parser_engine.format_recognizer import (
    FormatRecognizer,
    recognize_file_format,
)

# 导入类型判断层
from app.services.parser_engine.document_type_classifier import (
    DocumentTypeClassifier,
    classify_document_type,
)

# 导入引擎调度层
from app.services.parser_engine.parser_engine_dispatcher import (
    ParserEngineDispatcher,
    parse_file,
    extract_text_from_file,
    parse_with_rule_engine,
    parse_with_llm_engine,
    multi_llm_comparison,
    dual_engine_parallel_parse,
    handle_unrecognized_file,
    parse_result_to_source_document_result,
    ParserPerformanceMonitor,
    performance_monitor,
    get_performance_stats,
    reset_performance_stats,
)

# 导入规则解析器
from app.services.parser_engine.rule_parsers import (
    parse_invoice_rules,
    parse_bank_statement_rules,
    parse_contract_rules,
    parse_inventory_receipt_rules,
    parse_salary_table_rules,
    parse_expense_document_rules,
    parse_receipt_rules,
    parse_with_rules,
)

__all__ = [
    # 数据结构
    "FileFormat",
    "DocumentType",
    "DocumentSubType",
    "EngineType",
    "ParseResult",
    "LLMComparisonResult",
    "FormatRecognitionResult",
    "TypeClassificationResult",
    "UnrecognizedFile",
    
    # 标签映射
    "DOCUMENT_TYPE_LABELS",
    "DOCUMENT_SUB_TYPE_LABELS",
    "FILE_FORMAT_LABELS",
    
    # 格式识别层
    "FormatRecognizer",
    "recognize_file_format",
    
    # 类型判断层
    "DocumentTypeClassifier",
    "classify_document_type",
    
    # 引擎调度层
    "ParserEngineDispatcher",
    "parse_file",
    "extract_text_from_file",
    "parse_with_rule_engine",
    "parse_with_llm_engine",
    "multi_llm_comparison",
    "dual_engine_parallel_parse",
    "handle_unrecognized_file",
    "parse_result_to_source_document_result",
    
    # 性能监控
    "ParserPerformanceMonitor",
    "performance_monitor",
    "get_performance_stats",
    "reset_performance_stats",
]