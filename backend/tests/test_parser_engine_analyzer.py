# -*- coding: utf-8 -*-
"""
测试：双引擎对比分析工具

测试内容：
1. 字段标准化与别名映射
2. 值比较与冲突分类
3. 双引擎结果分析主函数
4. 合同结构化内容生成
5. 合规风险预审生成
6. 冲突热力图生成
7. 序列化输出

创建日期：2026-07-03
"""

import pytest
from decimal import Decimal

from app.services.doc_parsing.parser_engine.parse_result import DocumentType, EngineType, ParseResult
from app.services.doc_parsing.parser_engine.parser_engine_analyzer import (
    _build_field_mapping,
    _classify_conflict_type,
    _compare_values,
    _extract_numeric,
    _find_text_position,
    _is_numeric_value,
    _normalize_comparison_value,
    _normalize_field_name,
    analyze_dual_engine_result,
    report_to_dict,
)


# =============================================================================
# 测试 1：字段标准化
# =============================================================================

def test_normalize_field_name_with_standard_name():
    assert _normalize_field_name("contract_amount") == "contract_amount"


def test_normalize_field_name_with_alias():
    assert _normalize_field_name("合同金额") == "contract_amount"
    assert _normalize_field_name("合同总价") == "contract_amount"
    assert _normalize_field_name("甲方名称") == "party_a_name"


def test_build_field_mapping():
    data = {"合同金额": "10000", "甲方": "A公司"}
    mapping = _build_field_mapping(data)
    assert "contract_amount" in mapping
    assert "party_a_name" in mapping
    assert mapping["contract_amount"] == ["合同金额"]


# =============================================================================
# 测试 2：值标准化与比较
# =============================================================================

def test_normalize_comparison_value():
    assert _normalize_comparison_value("¥1,234.56元") == "1234.56"
    assert _normalize_comparison_value(None) == ""


def test_is_numeric_value():
    assert _is_numeric_value("1000.00") is True
    assert _is_numeric_value("¥1,000.00元") is True
    assert _is_numeric_value("A公司") is False


def test_extract_numeric():
    assert _extract_numeric("¥1,234.56元") == Decimal("1234.56")
    assert _extract_numeric("不是数字") is None


def test_compare_values_exact_match():
    is_consistent, conflict_type, severity = _compare_values("A公司", "A公司")
    assert is_consistent is True
    assert conflict_type == ""


def test_compare_values_amount_tolerance():
    is_consistent, conflict_type, severity = _compare_values("1000.00", "1000.50")
    assert is_consistent is True


def test_compare_values_amount_mismatch():
    is_consistent, conflict_type, severity = _compare_values("1000.00", "2000.00")
    assert is_consistent is False
    assert conflict_type == "value_mismatch"
    assert severity == "high"


def test_classify_conflict_type():
    assert _classify_conflict_type("contract_amount", "value_mismatch") == "amount_mismatch"
    assert _classify_conflict_type("sign_date", "value_mismatch") == "date_mismatch"
    assert _classify_conflict_type("party_a_name", "value_mismatch") == "party_mismatch"


# =============================================================================
# 测试 3：文本位置定位
# =============================================================================

def test_find_text_position():
    raw_text = "本合同编号为 HT2024001，甲方为 A公司，合同金额 10000 元。"
    position, snippet = _find_text_position(raw_text, "A公司")
    assert position is not None
    assert position > 0
    assert "A公司" in snippet


def test_find_text_position_not_found():
    raw_text = "本合同金额为 10000 元。"
    position, snippet = _find_text_position(raw_text, "不存在")
    assert position is None


# =============================================================================
# 测试 4：双引擎结果分析主函数
# =============================================================================

def _build_rule_result() -> ParseResult:
    return ParseResult(
        document_type=DocumentType.CONTRACT,
        data={
            "contract_no": "HT2024001",
            "contract_name": "设备采购合同",
            "party_a_name": "A公司",
            "party_b_name": "B公司",
            "sign_date": "2024-01-15",
            "contract_amount": "10000.00",
            "contract_term": "一年",
            "payment_terms": "月结30天",
            "project_name": "XX项目",
        },
        confidence=0.9,
        engine=EngineType.RULE,
        raw_text="合同编号 HT2024001，甲方 A公司，乙方 B公司，签订日期 2024-01-15，金额 10000.00 元，付款方式 月结30天。",
    )


def _build_llm_result() -> ParseResult:
    return ParseResult(
        document_type=DocumentType.CONTRACT,
        data={
            "合同编号": "HT2024001",
            "合同名称": "设备采购合同",
            "甲方": "A公司",
            "乙方": "B公司",
            "签订日期": "2024-01-15",
            "合同金额": "10000.00",
            "合同期限": "一年",
            "付款方式": "月结30天",
            "项目名称": "XX项目",
        },
        confidence=0.85,
        engine=EngineType.LLM,
        raw_text="合同编号 HT2024001，甲方 A公司，乙方 B公司，签订日期 2024-01-15，金额 10000.00 元，付款方式 月结30天。",
    )


def _build_conflicting_results() -> tuple[ParseResult, ParseResult]:
    rule = ParseResult(
        document_type=DocumentType.CONTRACT,
        data={
            "contract_no": "HT2024001",
            "party_a_name": "A公司",
            "party_b_name": "B公司",
            "contract_amount": "10000.00",
        },
        confidence=0.9,
        engine=EngineType.RULE,
        raw_text="合同编号 HT2024001，甲方 A公司，乙方 B公司，金额 10000.00 元。",
    )
    llm = ParseResult(
        document_type=DocumentType.CONTRACT,
        data={
            "合同编号": "HT2024001",
            "甲方": "A公司",
            "乙方": "C公司",
            "合同金额": "20000.00",
            "合同期限": "两年",
        },
        confidence=0.75,
        engine=EngineType.LLM,
        raw_text="合同编号 HT2024001，甲方 A公司，乙方 C公司，金额 20000.00 元，期限 两年。",
    )
    return rule, llm


def test_analyze_dual_engine_result_consistent():
    rule_result = _build_rule_result()
    llm_result = _build_llm_result()
    report = analyze_dual_engine_result(rule_result, llm_result, rule_result.raw_text)

    assert report.consistency_rate == 1.0
    assert len(report.conflict_fields) == 0
    assert len(report.consistent_fields) == 8
    assert report.stability_score > 0.8
    assert report.review_required is False
    assert report.contract_structured_content is not None
    assert report.contract_structured_content.contract_no == "HT2024001"
    assert report.compliance_risk_pre_review is not None
    assert report.compliance_risk_pre_review.risk_level == "low"


def test_analyze_dual_engine_result_conflicts():
    rule_result, llm_result = _build_conflicting_results()
    report = analyze_dual_engine_result(rule_result, llm_result, rule_result.raw_text)

    assert report.consistency_rate < 1.0
    assert len(report.conflict_fields) >= 2
    assert report.review_required is True
    assert report.stability_score < 0.8


def test_analyze_dual_engine_result_single_engine():
    rule_result = _build_rule_result()
    report = analyze_dual_engine_result(rule_result, None, rule_result.raw_text)

    assert report.consistency_rate == 0.0
    assert report.review_required is True
    assert "仅一个引擎返回结果" in report.review_reasons[0]


# =============================================================================
# 测试 5：冲突热力图
# =============================================================================

def test_conflict_heatmap():
    rule_result, llm_result = _build_conflicting_results()
    report = analyze_dual_engine_result(rule_result, llm_result, rule_result.raw_text)

    assert len(report.conflict_heatmap) > 0
    for cell in report.conflict_heatmap:
        assert cell.start_position >= 0
        assert cell.end_position > cell.start_position
        assert 0.0 <= cell.density <= 1.0


# =============================================================================
# 测试 6：合同结构化内容与合规风险预审
# =============================================================================

def test_contract_structured_content():
    rule_result, llm_result = _build_conflicting_results()
    report = analyze_dual_engine_result(rule_result, llm_result, rule_result.raw_text)

    content = report.contract_structured_content
    assert content is not None
    assert content.contract_no == "HT2024001"
    assert content.party_a_name == "A公司"
    assert content.review_required is True
    assert len(content.review_reasons) > 0


def test_compliance_risk_pre_review():
    rule_result, llm_result = _build_conflicting_results()
    report = analyze_dual_engine_result(rule_result, llm_result, rule_result.raw_text)

    review = report.compliance_risk_pre_review
    assert review is not None
    assert review.risk_level in {"low", "medium", "high", "critical"}
    assert len(review.risk_items) > 0


# =============================================================================
# 测试 7：序列化输出
# =============================================================================

def test_report_to_dict():
    rule_result, llm_result = _build_conflicting_results()
    report = analyze_dual_engine_result(rule_result, llm_result, rule_result.raw_text)
    result_dict = report_to_dict(report)

    assert "stability_score" in result_dict
    assert "conflict_heatmap" in result_dict
    assert "contract_structured_content" in result_dict
    assert "compliance_risk_pre_review" in result_dict
    assert isinstance(result_dict["conflict_heatmap"], list)
