# -*- coding: utf-8 -*-
"""
模块功能：解析引擎模块入口
业务场景：统一导出解析引擎的核心类、枚举和服务
政策依据：各类会计准则（CAS 1/9/14/22等）
创建日期：2026-06-26
"""

from .parse_result import (
    FileFormat,
    DocumentType,
    DocumentSubType,
    EngineType,
    ParseResult,
    LLMComparisonResult,
    FormatRecognitionResult,
    TypeClassificationResult,
    UnrecognizedFile,
    SealRecognitionResult,
    DOCUMENT_TYPE_LABELS,
    DOCUMENT_SUB_TYPE_LABELS,
    FILE_FORMAT_LABELS,
)

from .format_recognizer import FormatRecognizer, recognize_file_format

from .document_type_classifier import DocumentTypeClassifier, classify_document_type

from .parser_engine_dispatcher import (
    ParserEngineDispatcher,
    parse_file,
    ParserPerformanceMonitor,
    get_performance_stats,
    reset_performance_stats,
    performance_monitor,
)

from .config_service import get_runtime_parser_engine_config

from .parser_engine_analyzer import (
    FieldValueDetail,
    FieldConflictItem,
    FieldCoverageItem,
    ConflictHeatmapCell,
    ContractStructuredContent,
    ComplianceRiskItem,
    ComplianceRiskPreReview,
    EngineComparisonReport,
)

from .unified_parser_service import (
    convert_parse_result_to_dict,
    get_latest_source_file,
    build_parser_engine_summary,
    parse_source_file_with_unified_engine,
    mark_parser_engine_failure,
    mark_missing_source_file,
)

__all__ = [
    # 枚举类型
    'FileFormat',
    'DocumentType',
    'DocumentSubType',
    'EngineType',
    
    # 数据结构
    'ParseResult',
    'LLMComparisonResult',
    'FormatRecognitionResult',
    'TypeClassificationResult',
    'UnrecognizedFile',
    'SealRecognitionResult',
    
    # 标签映射
    'DOCUMENT_TYPE_LABELS',
    'DOCUMENT_SUB_TYPE_LABELS',
    'FILE_FORMAT_LABELS',
    
    # 服务类
    'FormatRecognizer',
    'DocumentTypeClassifier',
    'ParserEngineDispatcher',
    'get_runtime_parser_engine_config',
    
    # 函数
    'recognize_file_format',
    'classify_document_type',
    'parse_file',
    'get_performance_stats',
    'reset_performance_stats',
    
    # 性能监控
    'ParserPerformanceMonitor',
    'performance_monitor',
    'convert_parse_result_to_dict',
    'get_latest_source_file',
    'build_parser_engine_summary',
    'parse_source_file_with_unified_engine',
    'mark_parser_engine_failure',
    'mark_missing_source_file',
    
    # 分析器数据结构
    'FieldValueDetail',
    'FieldConflictItem',
    'FieldCoverageItem',
    'ConflictHeatmapCell',
    'ContractStructuredContent',
    'ComplianceRiskItem',
    'ComplianceRiskPreReview',
    'EngineComparisonReport',
]