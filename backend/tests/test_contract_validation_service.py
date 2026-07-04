# -*- coding: utf-8 -*-
"""合同字段校验与 LLM 推理服务单元测试"""

import json
from decimal import Decimal

import pytest

from app.services.basic_data.contract_validation_service import (
    ContractValidationReport,
    ContractValidationService,
    FieldInference,
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
)
from app.services.agent.llm_client_service import LLMResult


class FakeLLMClient:
    """模拟 LLM 客户端，用于控制推理返回值"""

    def __init__(
        self,
        response_content: str | None = None,
        available: bool = True,
        configured: bool = True,
    ):
        self.response_content = response_content
        self.available = available
        self.configured = configured

    def is_configured(self) -> bool:
        return self.configured

    def chat(self, messages, temperature=0.1) -> LLMResult:
        if not self.available:
            return LLMResult(available=False, error="LLM 不可用")
        return LLMResult(available=True, content=self.response_content, model="fake")


@pytest.fixture
def complete_contract():
    return {
        "contract_name": "技术服务合同",
        "party_a_name": "甲方科技有限公司",
        "party_b_name": "乙方软件有限公司",
        "sign_date": "2026-06-01",
        "contract_amount": 100000.00,
        "contract_amount_cn": "壹拾万元整",
        "contract_term": "2026-06-01 至 2027-05-31",
        "contract_type": "service",
        "payment_terms": "合同签订后支付 30%，验收后支付 70%",
        "contract_no": "HT-2026-001",
    }


@pytest.fixture
def service():
    return ContractValidationService(llm_client=FakeLLMClient())


def test_required_and_optional_field_lists():
    assert "contract_name" in REQUIRED_FIELDS
    assert "party_a_name" in REQUIRED_FIELDS
    assert "party_b_name" in REQUIRED_FIELDS
    assert "sign_date" in REQUIRED_FIELDS
    assert "contract_amount" in REQUIRED_FIELDS
    assert "contract_amount_cn" in REQUIRED_FIELDS
    assert "contract_term" in REQUIRED_FIELDS
    assert "contract_type" in REQUIRED_FIELDS
    assert "payment_terms" in REQUIRED_FIELDS

    assert "contract_no" in OPTIONAL_FIELDS
    assert "party_a_tax_id" in OPTIONAL_FIELDS
    assert "party_a_address" in OPTIONAL_FIELDS
    assert "party_b_tax_id" in OPTIONAL_FIELDS
    assert "party_b_address" in OPTIONAL_FIELDS
    assert "project_name" in OPTIONAL_FIELDS
    assert "liability_clause" in OPTIONAL_FIELDS


def test_complete_contract_returns_success(service, complete_contract):
    report = service.validate_and_infer(complete_contract)

    assert report.success is True
    assert report.status == "success_with_inference"
    assert report.missing_required_fields == []
    assert set(report.present_fields) == set(REQUIRED_FIELDS)
    assert report.final_data["contract_amount_cn"] == "壹拾万元整"
    assert report.inference_summary == "所有必填字段完整，无需推理。"


def test_missing_more_than_two_required_fields_triggers_manual(service):
    data = {
        "contract_name": "合同",
        # 缺失 party_a_name, party_b_name, sign_date, contract_amount ...
    }
    report = service.validate_and_infer(data)

    assert report.success is False
    assert report.status == "manual_intervention_required"
    assert len(report.missing_required_fields) > 2
    assert any("超过允许推理上限" in err for err in report.errors)


def test_payment_terms_object_is_normalized(service, complete_contract):
    complete_contract["payment_terms"] = {
        "prepayment": "30%",
        "final_payment": "70%",
        "milestone": "验收后",
    }
    report = service.validate_and_infer(complete_contract)

    assert report.success is True
    assert "prepayment: 30%" in report.final_data["payment_terms"]
    assert "final_payment: 70%" in report.final_data["payment_terms"]


def test_llm_inference_for_missing_fields(service, complete_contract):
    # 移除 contract_amount_cn 和 payment_terms，让 LLM 推理
    complete_contract["contract_amount_cn"] = ""
    complete_contract["payment_terms"] = None

    llm_response = {
        "inferences": [
            {
                "field_name": "contract_amount_cn",
                "inferred_value": "壹拾万元整",
                "reasoning": "contract_amount 为 100000.00，标准大写为壹拾万元整",
                "confidence": "high",
            },
            {
                "field_name": "payment_terms",
                "inferred_value": "合同签订后支付 30%，验收合格后支付 70%",
                "reasoning": "合同类型为 service，常见服务合同付款节奏为 30/70 分期",
                "confidence": "medium",
            },
        ],
        "uninferable_fields": [],
        "notes": "已补全 2 个字段",
    }
    service.llm = FakeLLMClient(response_content=json.dumps(llm_response, ensure_ascii=False))

    report = service.validate_and_infer(complete_contract)

    assert report.success is True
    assert report.status == "success_with_inference"
    assert report.final_data["contract_amount_cn"] == "壹拾万元整"
    assert "30%" in report.final_data["payment_terms"]
    assert len(report.inferences) == 2
    assert report.inferences[0].reasoning != ""


def test_fallback_number_to_chinese_when_llm_misses_cn(service, complete_contract):
    # LLM 没有推断 contract_amount_cn，但金额存在，应走本地兜底
    complete_contract["contract_amount_cn"] = ""

    llm_response = {
        "inferences": [],
        "uninferable_fields": ["contract_amount_cn"],
        "notes": "无法推断大写金额",
    }
    service.llm = FakeLLMClient(response_content=json.dumps(llm_response, ensure_ascii=False))

    report = service.validate_and_infer(complete_contract)

    assert report.success is True
    assert any(
        inf.field_name == "contract_amount_cn" and "壹拾万元整" in str(inf.inferred_value)
        for inf in report.inferences
    )


def test_uninferable_field_triggers_manual(service, complete_contract):
    # 缺失 contract_term，LLM 表示无法推断
    complete_contract["contract_term"] = ""

    llm_response = {
        "inferences": [],
        "uninferable_fields": ["contract_term"],
        "notes": "无起止日期线索",
    }
    service.llm = FakeLLMClient(response_content=json.dumps(llm_response, ensure_ascii=False))

    report = service.validate_and_infer(complete_contract)

    assert report.success is False
    assert report.status == "manual_intervention_required"
    assert "contract_term" in report.errors[0]


def test_llm_not_configured_triggers_manual(service, complete_contract):
    complete_contract["contract_amount_cn"] = ""
    service.llm = FakeLLMClient(configured=False)

    report = service.validate_and_infer(complete_contract)

    assert report.success is False
    assert report.status == "manual_intervention_required"
    assert any("LLM 推理未启用或未配置" in err for err in report.errors)


def test_disallow_llm_inference_triggers_manual(service, complete_contract):
    complete_contract["contract_amount_cn"] = ""

    report = service.validate_and_infer(complete_contract, allow_llm_inference=False)

    assert report.success is False
    assert report.status == "manual_intervention_required"


def test_format_report_text(service, complete_contract):
    report = service.validate_and_infer(complete_contract)
    text = service.format_report_text(report)

    assert "合同字段校验与推理报告" in text
    assert "最终状态：成功" in text
    assert "已填必填字段" in text
    assert "推理摘要" in text


def test_empty_payment_terms_list_normalized(service, complete_contract):
    complete_contract["payment_terms"] = []
    report = service.validate_and_infer(complete_contract)

    assert "payment_terms" in report.missing_required_fields


def test_parse_inference_response_with_non_json(service):
    response = LLMResult(available=True, content="```json\n{}\n```", model="fake")
    inferences, uninferable, notes = service._parse_inference_response(response)
    assert inferences == []
    assert uninferable == []


def test_field_inference_dataclass():
    inf = FieldInference(
        field_name="contract_amount_cn",
        inferred_value="壹拾万元整",
        reasoning="基于 contract_amount 转换",
        confidence="high",
    )
    assert inf.field_name == "contract_amount_cn"
    assert inf.confidence == "high"


def test_normalize_payment_terms_list_of_dicts(service):
    """payment_terms 为列表对象时应被规范化为文本"""
    value = [
        {"stage": "预付款", "ratio": "30%"},
        {"stage": "尾款", "ratio": "70%"},
    ]
    normalized, _ = service._normalize_payment_terms(value)
    assert "stage: 预付款" in normalized
    assert "stage: 尾款" in normalized
    assert " | " in normalized


def test_number_to_chinese_negative_returns_empty(service):
    assert service._number_to_chinese(Decimal("-100")) == ""


def test_number_to_chinese_invalid_input_returns_empty(service):
    assert service._number_to_chinese("not_a_number") == ""


def test_number_to_chinese_with_jiao_fen(service):
    assert service._number_to_chinese(Decimal("100.56")) == "壹佰元伍角陆分"


def test_number_to_chinese_with_jiao_only(service):
    assert service._number_to_chinese(Decimal("100.50")) == "壹佰元伍角"


def test_parse_inference_response_no_json_match(service):
    response = LLMResult(available=True, content="完全没有 JSON 内容", model="fake")
    inferences, uninferable, notes = service._parse_inference_response(response)
    assert inferences == []
    assert "格式错误" in notes


def test_format_report_text_empty_inferences_and_errors(service):
    report = ContractValidationReport(
        success=True,
        status="success_with_inference",
        present_fields=["contract_name"],
        inference_summary="无需推理",
    )
    text = service.format_report_text(report)
    assert "推理过程：" in text
    assert "无" in text
    assert "错误/提示：" not in text
