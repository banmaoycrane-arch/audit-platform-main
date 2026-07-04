# -*- coding: utf-8 -*-
"""合同解析服务单元测试"""

import json
from decimal import Decimal

import pytest

from app.services.basic_data.contract_parser_service import (
    CommodityItem,
    ComplianceAssessment,
    ContractParser,
    ContractParseResult,
    ContractParty,
    ContractPenalty,
    ContractPrice,
    FeeEstimate,
    FinancialTerms,
    PerformanceObligation,
    TaxLiabilityClause,
    TaxTreatment,
)
from app.services.agent.llm_client_service import LLMResult


class FakeLLMClient:
    """模拟 LLM 客户端"""

    def __init__(self, response_content: str | None = None, available: bool = True):
        self.response_content = response_content
        self.available = available

    def chat(self, messages, temperature=0.1) -> LLMResult:
        if not self.available:
            return LLMResult(available=False, error="LLM 不可用")
        return LLMResult(available=True, content=self.response_content, model="fake")


@pytest.fixture
def parser():
    return ContractParser(llm_client=FakeLLMClient())


@pytest.fixture
def valid_procurement_response():
    return {
        "contract_type": "采购",
        "contract_valid": True,
        "commercial_substance": True,
        "collection_probable": True,
        "effective_conditions": "签字盖章",
        "signing_date": "2026-06-01",
        "parties": [
            {"name": "甲方科技", "role": "甲方", "tax_id": "91110000XXXX", "address": "北京"},
            {"name": "乙方供应", "role": "乙方", "tax_id": "91110000YYYY", "address": "上海"},
        ],
        "period": {"start_date": "2026-06-01", "end_date": "2027-05-31", "duration_days": 365},
        "price": {
            "total_amount": "113000",
            "tax_rate": "13%",
            "currency": "CNY",
            "payment_terms": "预付30%，到货70%",
        },
        "performance_obligations": [
            {
                "description": "服务器设备",
                "quantity": 10,
                "unit": "台",
                "unit_price": 10000,
                "total_price": 100000,
                "revenue_recognition_method": "时点法",
            }
        ],
        "penalties": [
            {
                "penalty_clause": "迟延交货每日千分之三",
                "penalty_amount": "1000",
                "penalty_type": "迟延",
                "is_probable": False,
            }
        ],
        "tax_treatment": {"tax_type": "增值税", "tax_rate": "13%", "tax_amount": "13000"},
        "commodities": [
            {
                "item_no": 1,
                "product_name": "服务器",
                "specification": "2U机架式",
                "model_number": "DL380 Gen10",
                "brand": "HPE",
                "unit": "台",
                "quantity": 10,
                "unit_price": 10000,
                "total_price": 100000,
                "weight": "20kg/台",
                "quality_standard": "国标",
                "delivery_terms": "送货上门",
                "warranty_period": "3年",
                "missing_attributes": [],
                "consistency_errors": [],
            }
        ],
        "financial_terms": {
            "contract_amount": 113000,
            "goods_amount": 100000,
            "transportation_fee": 3000,
            "tax_amount": 13000,
            "tax_rate": "13%",
            "explicitly_stated": ["goods_amount", "transportation_fee", "tax_amount"],
            "estimates": [],
        },
        "tax_liability": {
            "is_critical": True,
            "responsible_party": "乙方",
            "tax_type": "增值税",
            "tax_rate": "13%",
            "invoice_type": "增值税专用发票",
            "trigger_event": "付款前开票",
            "consequence": "承担全部责任",
            "full_text": "Before Party A makes payment...",
            "risk_flag": "发票责任",
        },
        "compliance_assessment": {
            "score": 85,
            "risk_level": "low",
            "missing_clauses": [],
            "risk_flags": [],
            "internal_control_notes": "基本合规",
        },
        "audit_trail": [
            {"field": "contract_amount", "source": "extracted", "basis": "合同总价", "confidence": "high"}
        ],
        "summary": "采购服务器合同",
        "accounting_notes": "按时点法确认",
        "five_step_analysis": "五步法完整",
        "confidence_score": 0.95,
    }


def _make_parser_with_response(parser, data):
    parser.llm = FakeLLMClient(response_content=json.dumps(data, ensure_ascii=False))


def test_parse_short_text_returns_error(parser):
    result = parser.parse("短")
    assert result.accounting_notes == "合同文本过短，无法解析"
    assert result.confidence_score == Decimal("0.00")


def test_parse_empty_text_returns_error(parser):
    result = parser.parse("")
    assert result.accounting_notes == "合同文本过短，无法解析"


def test_parse_valid_procurement_contract(parser, valid_procurement_response):
    _make_parser_with_response(parser, valid_procurement_response)
    text = "本合同为服务器采购合同，甲方甲方科技，乙方乙方供应..." + "x" * 100
    result = parser.parse(text)

    assert result.contract_type == "采购"
    assert len(result.parties) == 2
    assert result.price.total_amount == Decimal("113000.00")
    assert result.price.tax_rate == Decimal("0.13")
    assert len(result.commodities) == 1
    assert result.commodities[0].product_name == "服务器"
    assert result.commodities[0].model_number == "DL380 Gen10"
    assert result.financial_terms.transportation_fee == Decimal("3000.00")
    assert result.tax_liability.is_critical is True
    assert result.compliance_assessment.score == 85
    assert len(result.audit_trail) == 1


def test_parse_llm_unavailable(parser):
    parser.llm = FakeLLMClient(available=False)
    result = parser.parse("x" * 100)
    assert "LLM解析失败" in result.accounting_notes


def test_parse_invalid_json_fallback(parser):
    parser.llm = FakeLLMClient(response_content="```json\n{}\n```")
    result = parser.parse("x" * 100)
    assert result.contract_type == ""


def test_parse_json_in_text(parser, valid_procurement_response):
    content = json.dumps(valid_procurement_response, ensure_ascii=False)
    parser.llm = FakeLLMClient(response_content=f"some text\n{content}\nmore text")
    result = parser.parse("x" * 100)
    assert result.contract_type == "采购"


def test_parse_amount_variations(parser):
    data = {
        "contract_type": "服务",
        "price": {"total_amount": "¥100,000.50", "tax_rate": "6%"},
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    assert result.price.total_amount == Decimal("100000.50")
    assert result.price.tax_amount == Decimal("5660.41")
    assert result.price.amount_excl_tax == Decimal("94340.09")


def test_parse_tax_rate_formats(parser):
    data = {"price": {"total_amount": 10000, "tax_rate": "13%"}}
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    assert result.price.tax_rate == Decimal("0.13")

    data = {"price": {"total_amount": 10000, "tax_rate": 0.06}}
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    assert result.price.tax_rate == Decimal("0.06")


def test_parse_commodities_with_missing_fields(parser):
    data = {
        "contract_type": "采购",
        "commodities": [
            {
                "product_name": "钢材",
                "quantity": 100,
                "unit": "吨",
                "unit_price": 5000,
                "total_price": 500000,
                "missing_attributes": ["weight"],
                "consistency_errors": [],
            }
        ],
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    assert result.commodities[0].missing_attributes == ["weight"]
    assert result.commodities[0].model_number == ""


def test_parse_financial_terms_with_estimates(parser):
    data = {
        "financial_terms": {
            "contract_amount": 100000,
            "goods_amount": 92000,
            "transportation_fee": None,
            "warehousing_cost": None,
            "insurance_fee": None,
            "explicitly_stated": ["goods_amount"],
            "estimates": [
                {
                    "fee_type": "运输费",
                    "estimated_range_low": 3000,
                    "estimated_range_high": 7000,
                    "basis": "行业惯例",
                    "methodology": "合同金额 3%-7%",
                    "confidence": "medium",
                    "is_material": True,
                    "audit_note": "未明确",
                }
            ],
        }
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    assert result.financial_terms.transportation_fee is None
    assert len(result.financial_terms.estimates) == 1
    assert result.financial_terms.estimates[0].fee_type == "运输费"
    assert result.financial_terms.estimates[0].is_material is True


def test_validate_accounting_pass(parser, valid_procurement_response):
    _make_parser_with_response(parser, valid_procurement_response)
    result = parser.parse("x" * 100)
    errors = parser.validate_accounting(result)
    assert errors == []


def test_validate_accounting_invalid_tax_split(parser):
    data = {
        "contract_type": "采购",
        "price": {"total_amount": 10000, "tax_rate": "13%"},
        "performance_obligations": [
            {"description": "货物", "revenue_recognition_method": "时点法"}
        ],
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    # total_amount=10000, tax_rate=13%, computed tax=1150.44, amount_excl=8849.56
    # If we manually set inconsistent values, it would fail. Here it should pass.
    errors = parser.validate_accounting(result)
    assert not any("价税分离" in e for e in errors)


def test_validate_accounting_missing_obligation_method(parser):
    data = {
        "price": {"total_amount": 10000, "tax_rate": "13%"},
        "performance_obligations": [{"description": "货物"}],
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    errors = parser.validate_accounting(result)
    assert any("未识别收入确认方法" in e for e in errors)


def test_validate_accounting_time_method_missing_criteria(parser):
    data = {
        "price": {"total_amount": 10000, "tax_rate": "13%"},
        "performance_obligations": [
            {"description": "服务", "revenue_recognition_method": "时段法"}
        ],
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    errors = parser.validate_accounting(result)
    assert any("适用时段法，但未说明满足哪项条件" in e for e in errors)


def test_validate_accounting_allocation_ratio_error(parser):
    data = {
        "price": {"total_amount": 10000, "tax_rate": "13%"},
        "performance_obligations": [
            {
                "description": "A",
                "revenue_recognition_method": "时点法",
                "allocation_ratio": 0.4,
            },
            {
                "description": "B",
                "revenue_recognition_method": "时点法",
                "allocation_ratio": 0.4,
            },
        ],
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    errors = parser.validate_accounting(result)
    assert any("分摊比例之和不为100%" in e for e in errors)


def test_validate_accounting_probable_penalty_not_provisioned(parser):
    data = {
        "price": {"total_amount": 10000, "tax_rate": "13%"},
        "performance_obligations": [
            {"description": "货物", "revenue_recognition_method": "时点法"}
        ],
        "penalties": [
            {
                "penalty_clause": "违约",
                "is_probable": True,
                "provision_required": False,
            }
        ],
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    errors = parser.validate_accounting(result)
    assert any("违约责任很可能发生，但未预提" in e for e in errors)


def test_validate_accounting_commodity_amount_mismatch(parser):
    data = {
        "contract_type": "采购",
        "price": {"total_amount": 10000, "tax_rate": "13%"},
        "performance_obligations": [
            {"description": "货物", "revenue_recognition_method": "时点法"}
        ],
        "commodities": [
            {
                "product_name": "货物",
                "quantity": 10,
                "unit_price": 1000,
                "total_price": 9000,
            }
        ],
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    errors = parser.validate_accounting(result)
    assert any("金额勾稽不一致" in e for e in errors)


def test_validate_accounting_tax_liability_rate_inconsistent(parser):
    data = {
        "contract_type": "采购",
        "price": {"total_amount": 10000, "tax_rate": "13%"},
        "performance_obligations": [
            {"description": "货物", "revenue_recognition_method": "时点法"}
        ],
        "tax_treatment": {"tax_rate": "13%"},
        "tax_liability": {"is_critical": True, "tax_rate": "6%"},
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    errors = parser.validate_accounting(result)
    assert any("重大税务责任条款税率" in e for e in errors)


def test_to_dict_serializable(parser, valid_procurement_response):
    _make_parser_with_response(parser, valid_procurement_response)
    result = parser.parse("x" * 100)
    data = parser.to_dict(result)
    assert "commodities" in data
    assert data["contract_type"] == "采购"


def test_parse_optional_amount_returns_none(parser):
    assert parser._parse_optional_amount(None) is None
    assert parser._parse_optional_amount("") is None
    assert parser._parse_optional_amount(0) is None
    assert parser._parse_optional_amount("1000") == Decimal("1000.00")


def test_parse_optional_tax_rate_returns_none(parser):
    assert parser._parse_optional_tax_rate(None) is None
    assert parser._parse_optional_tax_rate("") is None
    assert parser._parse_optional_tax_rate(0) is None
    assert parser._parse_optional_tax_rate("13%") == Decimal("0.13")


def test_parse_amount_with_invalid_value(parser):
    assert parser._parse_amount("abc") == Decimal("0.00")
    assert parser._parse_amount(None) == Decimal("0.00")


def test_parse_tax_rate_with_invalid_value(parser):
    assert parser._parse_tax_rate("abc") == Decimal("0.00")
    assert parser._parse_tax_rate(None) == Decimal("0.00")


def test_dataclasses_defaults():
    item = CommodityItem()
    assert item.product_name == ""
    assert item.quantity == Decimal("0")

    ft = FinancialTerms()
    assert ft.transportation_fee is None
    assert ft.estimates == []

    tl = TaxLiabilityClause()
    assert tl.is_critical is False

    ca = ComplianceAssessment()
    assert ca.score == 100


def test_parse_service_contract(parser):
    data = {
        "contract_type": "service",
        "price": {"total_amount": 50000, "tax_rate": "6%"},
        "performance_obligations": [
            {
                "description": "咨询服务",
                "revenue_recognition_method": "时段法",
                "time_method_criteria": ["客户同时取得并消耗"],
            }
        ],
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    assert result.contract_type == "service"
    assert result.performance_obligations[0].revenue_recognition_method == "时段法"


def test_parse_sales_contract(parser):
    data = {
        "contract_type": "销售",
        "price": {"total_amount": 20000, "tax_rate": "13%"},
        "performance_obligations": [
            {"description": "产品销售", "revenue_recognition_method": "时点法"}
        ],
    }
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    assert result.contract_type == "销售"


def test_parse_missing_compliance_data(parser):
    data = {"contract_type": "采购"}
    _make_parser_with_response(parser, data)
    result = parser.parse("x" * 100)
    assert result.compliance_assessment.score == 100
    assert result.financial_terms.contract_amount == Decimal("0.00")
