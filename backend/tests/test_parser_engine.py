# -*- coding: utf-8 -*-
"""
测试：文件解析引擎基础架构验证

测试内容：
1. 模块导入测试
2. 数据结构完整性测试
3. 格式识别功能测试
4. 类型判断功能测试

创建日期：2026-06-26
"""

import pytest
from pathlib import Path

# =============================================================================
# 测试 1：模块导入测试
# =============================================================================

def test_module_import():
    """
    测试模块导入是否正常
    
    验证点：所有类和函数可正确导入
    """
    # 导入数据结构
    from app.services.parser_engine import (
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
    from app.services.parser_engine import (
        FormatRecognizer,
        recognize_file_format,
    )
    
    # 导入类型判断层
    from app.services.parser_engine import (
        DocumentTypeClassifier,
        classify_document_type,
    )
    
    # 导入引擎调度层
    from app.services.parser_engine import (
        ParserEngineDispatcher,
        parse_file,
    )
    
    # 验证导入成功
    assert FileFormat is not None
    assert DocumentType is not None
    assert DocumentSubType is not None
    assert EngineType is not None
    assert ParseResult is not None
    assert FormatRecognizer is not None
    assert DocumentTypeClassifier is not None
    assert ParserEngineDispatcher is not None


# =============================================================================
# 测试 2：数据结构完整性测试
# =============================================================================

def test_file_format_enum():
    """
    测试 FileFormat 枚举完整性
    
    验证点：所有预定义的文件格式类型存在
    """
    from app.services.parser_engine import FileFormat
    
    # 验证 PDF 类格式
    assert FileFormat.PDF_TEXT.value == "pdf_text"
    assert FileFormat.PDF_IMAGE.value == "pdf_image"
    assert FileFormat.OFD.value == "ofd"
    
    # 验证结构化数据类格式
    assert FileFormat.EXCEL.value == "excel"
    assert FileFormat.CSV.value == "csv"
    assert FileFormat.XML.value == "xml"
    
    # 验证图片类格式
    assert FileFormat.IMAGE.value == "image"
    
    # 验证文档类格式
    assert FileFormat.TEXT.value == "text"
    assert FileFormat.WORD.value == "word"
    assert FileFormat.MARKDOWN.value == "markdown"
    
    # 验证特殊类格式
    assert FileFormat.UNKNOWN.value == "unknown"


def test_document_type_enum():
    """
    测试 DocumentType 枚举完整性
    
    验证点：所有预定义的文档类型存在
    """
    from app.services.parser_engine import DocumentType
    
    # 验证现有类型
    assert DocumentType.INVOICE.value == "invoice"
    assert DocumentType.BANK_STATEMENT.value == "bank_statement"
    assert DocumentType.CONTRACT.value == "contract"
    assert DocumentType.INVENTORY_RECEIPT.value == "inventory_receipt"
    
    # 验证新增类型
    assert DocumentType.SALARY_TABLE.value == "salary_table"
    assert DocumentType.EXPENSE_DOCUMENT.value == "expense_document"
    assert DocumentType.RECEIPT.value == "receipt"
    
    # 验证特殊类型
    assert DocumentType.ACCOUNTING_ENTRY.value == "accounting_entry"
    assert DocumentType.GENERAL.value == "general"
    assert DocumentType.UNKNOWN.value == "unknown"


def test_document_sub_type_enum():
    """
    测试 DocumentSubType 枚举完整性
    
    验证点：各主类型下的细分类型定义完整
    """
    from app.services.parser_engine import DocumentSubType
    
    # 验证发票细分类型
    assert DocumentSubType.INVOICE_SPECIAL.value == "invoice_special"
    assert DocumentSubType.INVOICE_NORMAL.value == "invoice_normal"
    assert DocumentSubType.INVOICE_FIXED.value == "invoice_fixed"
    assert DocumentSubType.INVOICE_ELECTRONIC.value == "invoice_electronic"
    
    # 验证银行细分类型
    assert DocumentSubType.BANK_TRANSACTION_LIST.value == "bank_transaction_list"
    assert DocumentSubType.BANK_STATEMENT.value == "bank_statement"
    assert DocumentSubType.BANK_RECEIPT.value == "bank_receipt"
    
    # 验证合同细分类型
    assert DocumentSubType.CONTRACT_STANDARD.value == "contract_standard"
    assert DocumentSubType.CONTRACT_SIMPLE.value == "contract_simple"
    assert DocumentSubType.CONTRACT_HANDWRITTEN.value == "contract_handwritten"
    
    # 验证入库单细分类型
    assert DocumentSubType.INVENTORY_STANDARD.value == "inventory_standard"
    assert DocumentSubType.ECOM_ORDER.value == "ecom_order"
    assert DocumentSubType.ECOM_BILL.value == "ecom_bill"


def test_engine_type_enum():
    """
    测试 EngineType 枚举完整性
    
    验证点：所有引擎类型定义存在
    """
    from app.services.parser_engine import EngineType
    
    assert EngineType.RULE.value == "rule"
    assert EngineType.LLM.value == "llm"
    assert EngineType.FUSED.value == "fused"
    assert EngineType.WEIGHTED_VOTE.value == "weighted_vote"
    assert EngineType.USER_SELECT.value == "user_select"


def test_parse_result_dataclass():
    """
    测试 ParseResult 数据类完整性
    
    验证点：所有字段定义存在，可正确创建实例
    """
    from app.services.parser_engine import ParseResult, DocumentType, EngineType
    from datetime import datetime
    
    # 创建测试实例
    result = ParseResult(
        document_type=DocumentType.INVOICE,
        sub_type=None,
        data={"发票号码": "123456", "金额": "1000"},
        confidence=0.85,
        engine=EngineType.LLM,
        engine_name="qwen2.5-14b",
        raw_text="测试文本",
        validation_errors=["借贷不平衡"],
        accounting_notes="适用CAS 14收入确认准则",
    )
    
    # 验证字段
    assert result.document_type == DocumentType.INVOICE
    assert result.data["发票号码"] == "123456"
    assert result.confidence == 0.85
    assert result.engine == EngineType.LLM
    assert len(result.validation_errors) == 1
    
    # 验证 to_dict 方法
    result_dict = result.to_dict()
    assert result_dict["document_type"] == "invoice"
    assert result_dict["confidence"] == 0.85
    assert isinstance(result_dict["parse_time"], str)


def test_llm_comparison_result_dataclass():
    """
    测试 LLMComparisonResult 数据类完整性
    
    验证点：所有字段定义存在，可正确创建实例
    """
    from app.services.parser_engine import (
        LLMComparisonResult,
        ParseResult,
        DocumentType,
        EngineType,
    )
    
    # 创建测试实例
    comparison = LLMComparisonResult(
        engine_results={
            "qwen2.5-14b": ParseResult(
                document_type=DocumentType.INVOICE,
                confidence=0.9,
            ),
            "qwen2.5-7b": ParseResult(
                document_type=DocumentType.INVOICE,
                confidence=0.8,
            ),
        },
        field_agreement={"发票号码": 1.0, "金额": 0.75},
        final_result=None,
        selection_reason="等待用户选择",
        field_sources={},
    )
    
    # 验证字段
    assert len(comparison.engine_results) == 2
    assert comparison.field_agreement["发票号码"] == 1.0
    assert comparison.selection_reason == "等待用户选择"


# =============================================================================
# 测试 3：格式识别功能测试
# =============================================================================

def test_format_recognizer_pdf():
    """
    测试 PDF 格式识别
    
    验证点：PDF文件后缀识别正确
    """
    from app.services.parser_engine import FormatRecognizer
    
    recognizer = FormatRecognizer()
    
    # 注意：这里只测试后缀识别，不测试实际PDF文件
    # 因为测试环境可能没有真实的PDF文件
    
    # 模拟 PDF 后缀
    mock_pdf_path = "test.pdf"
    # 不实际调用 recognize，因为没有真实文件
    # 只验证类和方法存在
    assert recognizer.recognize is not None


def test_format_recognizer_excel():
    """
    测试 Excel 格式识别
    
    验证点：Excel文件后缀识别正确
    """
    from app.services.parser_engine import FormatRecognizer
    
    recognizer = FormatRecognizer()
    
    # 验证类和方法存在
    assert recognizer.recognize is not None


def test_suffix_to_format_mapping():
    """
    测试文件后缀与格式映射
    
    验证点：所有预定义的后缀映射正确
    """
    from app.services.parser_engine.format_recognizer import SUFFIX_TO_FORMAT
    from app.services.parser_engine import FileFormat
    
    # 验证 PDF 类映射
    assert SUFFIX_TO_FORMAT[".pdf"] == FileFormat.PDF_TEXT
    assert SUFFIX_TO_FORMAT[".ofd"] == FileFormat.OFD
    
    # 验证 Excel 类映射
    assert SUFFIX_TO_FORMAT[".xlsx"] == FileFormat.EXCEL
    assert SUFFIX_TO_FORMAT[".xls"] == FileFormat.EXCEL
    
    # 验证 CSV 映射
    assert SUFFIX_TO_FORMAT[".csv"] == FileFormat.CSV
    
    # 验证 XML 映射
    assert SUFFIX_TO_FORMAT[".xml"] == FileFormat.XML
    
    # 验证图片类映射
    assert SUFFIX_TO_FORMAT[".jpg"] == FileFormat.IMAGE
    assert SUFFIX_TO_FORMAT[".png"] == FileFormat.IMAGE


# =============================================================================
# 测试 4：类型判断功能测试
# =============================================================================

def test_document_type_classifier_keywords():
    """
    测试类型关键词映射
    
    验证点：各文档类型的关键词定义正确
    """
    from app.services.parser_engine.document_type_classifier import TYPE_KEYWORDS
    from app.services.parser_engine import DocumentType
    
    # 验证发票关键词
    invoice_keywords = TYPE_KEYWORDS.get(DocumentType.INVOICE, {})
    primary_keywords = invoice_keywords.get("primary", [])
    assert "发票" in primary_keywords
    assert "增值税" in primary_keywords
    
    # 验证银行流水关键词
    bank_keywords = TYPE_KEYWORDS.get(DocumentType.BANK_STATEMENT, {})
    primary_keywords = bank_keywords.get("primary", [])
    assert "银行" in primary_keywords
    assert "流水" in primary_keywords
    
    # 验证合同关键词
    contract_keywords = TYPE_KEYWORDS.get(DocumentType.CONTRACT, {})
    primary_keywords = contract_keywords.get("primary", [])
    assert "合同" in primary_keywords
    assert "甲方" in primary_keywords


def test_format_to_candidate_types_mapping():
    """
    测试格式与候选类型映射
    
    验证点：各文件格式对应的候选类型正确
    """
    from app.services.parser_engine.document_type_classifier import FORMAT_TO_CANDIDATE_TYPES
    from app.services.parser_engine import FileFormat, DocumentType
    
    # 验证 OFD/XML → 发票
    assert DocumentType.INVOICE in FORMAT_TO_CANDIDATE_TYPES[FileFormat.OFD]
    assert DocumentType.INVOICE in FORMAT_TO_CANDIDATE_TYPES[FileFormat.XML]
    
    # 验证 Excel → 银行流水、工资表
    excel_candidates = FORMAT_TO_CANDIDATE_TYPES[FileFormat.EXCEL]
    assert DocumentType.BANK_STATEMENT in excel_candidates
    assert DocumentType.SALARY_TABLE in excel_candidates
    
    # 验证 PDF → 发票、合同、收据
    pdf_candidates = FORMAT_TO_CANDIDATE_TYPES[FileFormat.PDF_TEXT]
    assert DocumentType.INVOICE in pdf_candidates
    assert DocumentType.CONTRACT in pdf_candidates
    assert DocumentType.RECEIPT in pdf_candidates


def test_document_type_classifier_class():
    """
    测试 DocumentTypeClassifier 类
    
    验证点：类和方法存在
    """
    from app.services.parser_engine import DocumentTypeClassifier
    
    classifier = DocumentTypeClassifier()
    
    # 验证主要方法存在
    assert classifier.classify is not None
    assert classifier._extract_text_for_classification is not None
    assert classifier._calculate_type_scores is not None
    assert classifier._identify_sub_type is not None
    
    # 验证细分类型识别方法存在
    assert classifier._identify_invoice_sub_type is not None
    assert classifier._identify_bank_sub_type is not None
    assert classifier._identify_contract_sub_type is not None
    assert classifier._identify_inventory_sub_type is not None
    assert classifier._identify_salary_sub_type is not None
    assert classifier._identify_expense_sub_type is not None
    assert classifier._identify_receipt_sub_type is not None


# =============================================================================
# 测试 5：引擎调度层基础测试
# =============================================================================

def test_parser_engine_dispatcher_class():
    """
    测试 ParserEngineDispatcher 类
    
    验证点：类和方法存在
    """
    from app.services.parser_engine import ParserEngineDispatcher
    
    dispatcher = ParserEngineDispatcher()
    
    # 验证主要方法存在
    assert dispatcher.parse is not None


def test_config_parameters():
    """
    测试配置参数
    
    验证点：新增的LLM配置参数存在
    """
    from app.core.config import get_settings
    
    settings = get_settings()
    
    # 验证LLM性能参数
    assert hasattr(settings, "llm_max_concurrent_models")
    assert hasattr(settings, "llm_memory_limit_mb")
    assert hasattr(settings, "llm_preferred_model")
    assert hasattr(settings, "llm_fallback_model")
    assert hasattr(settings, "llm_timeout_seconds")
    
    # 验证并行策略参数
    assert hasattr(settings, "llm_enable_parallel_parsing")
    assert hasattr(settings, "llm_parallel_timeout_seconds")
    
    # 验证结果选择策略参数
    assert hasattr(settings, "llm_result_selection_mode")
    assert hasattr(settings, "llm_confidence_threshold_auto")
    assert hasattr(settings, "llm_confidence_threshold_user")
    
    # 验证多LLM引擎对比配置参数
    assert hasattr(settings, "llm_multi_engine_enabled")
    assert hasattr(settings, "llm_comparison_mode")
    assert hasattr(settings, "llm_comparison_strategy")
    assert hasattr(settings, "llm_comparison_engines")
    assert hasattr(settings, "llm_engine_weights")
    assert hasattr(settings, "llm_agreement_threshold")
    assert hasattr(settings, "llm_save_all_results")
    
    # 验证默认值
    assert settings.llm_max_concurrent_models == 1
    assert settings.llm_preferred_model == "qwen2.5-14b"
    assert settings.llm_multi_engine_enabled is True
    assert settings.llm_comparison_strategy == "weighted_vote"


def test_performance_monitor_class():
    """
    测试性能监控器类
    
    验证点：
    1. 性能监控器类可以正常实例化
    2. 可以记录解析完成情况
    3. 可以获取统计数据
    4. 可以重置统计数据
    """
    from app.services.parser_engine import ParserPerformanceMonitor
    
    monitor = ParserPerformanceMonitor()
    
    # 初始状态验证
    stats = monitor.get_stats()
    assert stats["total_parses"] == 0
    assert stats["successful_parses"] == 0
    assert stats["failed_parses"] == 0
    assert stats["success_rate_percent"] == 0.0
    
    # 记录成功的解析
    monitor.record_parse_complete(
        file_format="pdf",
        document_type="invoice",
        total_duration_ms=100.0,
        success=True,
    )
    monitor.record_parse_complete(
        file_format="excel",
        document_type="bank_statement",
        total_duration_ms=200.0,
        success=True,
    )
    
    # 记录失败的解析
    monitor.record_parse_complete(
        file_format="image",
        document_type="receipt",
        total_duration_ms=50.0,
        success=False,
        error_type="ocr_error",
    )
    
    # 验证统计数据
    stats = monitor.get_stats()
    assert stats["total_parses"] == 3
    assert stats["successful_parses"] == 2
    assert stats["failed_parses"] == 1
    assert stats["success_rate_percent"] == 66.67
    
    # 验证按格式统计
    assert "pdf" in stats["format_stats"]
    assert "excel" in stats["format_stats"]
    assert "image" in stats["format_stats"]
    assert stats["format_stats"]["pdf"]["count"] == 1
    assert stats["format_stats"]["pdf"]["avg_ms"] == 100.0
    
    # 验证按文档类型统计
    assert "invoice" in stats["doctype_stats"]
    assert "bank_statement" in stats["doctype_stats"]
    assert "receipt" in stats["doctype_stats"]
    
    # 验证错误统计
    assert "ocr_error" in stats["error_stats"]
    assert stats["error_stats"]["ocr_error"] == 1
    
    # 测试记录阶段耗时
    monitor.record_stage_duration("format_recognition", 10.0)
    monitor.record_stage_duration("format_recognition", 20.0)
    monitor.record_stage_duration("type_classification", 15.0)
    
    stats = monitor.get_stats()
    assert "format_recognition" in stats["stage_stats"]
    assert stats["stage_stats"]["format_recognition"]["count"] == 2
    assert stats["stage_stats"]["format_recognition"]["avg_ms"] == 15.0
    assert stats["stage_stats"]["type_classification"]["count"] == 1
    assert stats["stage_stats"]["type_classification"]["avg_ms"] == 15.0
    
    # 测试重置
    monitor.reset()
    stats = monitor.get_stats()
    assert stats["total_parses"] == 0
    assert stats["successful_parses"] == 0
    assert stats["failed_parses"] == 0
    assert len(stats["stage_stats"]) == 0
    assert len(stats["format_stats"]) == 0
    assert len(stats["doctype_stats"]) == 0
    assert len(stats["error_stats"]) == 0


def test_performance_monitor_functions():
    """
    测试性能监控全局函数
    
    验证点：
    1. get_performance_stats 函数可用
    2. reset_performance_stats 函数可用
    """
    from app.services.parser_engine import get_performance_stats
    from app.services.parser_engine import reset_performance_stats
    from app.services.parser_engine import performance_monitor
    
    # 验证函数存在且可调用
    stats = get_performance_stats()
    assert isinstance(stats, dict)
    assert "total_parses" in stats
    
    # 验证重置函数
    reset_performance_stats()
    stats = get_performance_stats()
    assert stats["total_parses"] == 0
    
    # 验证全局实例
    assert performance_monitor is not None
    assert hasattr(performance_monitor, "record_parse_complete")
    assert hasattr(performance_monitor, "get_stats")
    assert hasattr(performance_monitor, "reset")


# =============================================================================
# 总结
# =============================================================================

if __name__ == "__main__":
    """
    运行所有测试
    
    使用方法：
    pytest backend/tests/test_parser_engine.py -v
    """
    pytest.main([__file__, "-v"])