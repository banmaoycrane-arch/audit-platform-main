"""底稿语义分解引擎测试。"""

from app.services.draft_semantic_decomposition_service import decompose_draft
from app.services.llm_client_service import LLMResult
from app.services.source_document_service import SourceDocumentResult


def _contract_classification(text: str) -> SourceDocumentResult:
    return SourceDocumentResult(
        document_type="contract",
        confidence=0.92,
        data={
            "contract_number": "CG-2026-100",
            "party_a": "本公司",
            "party_b": "供应商A",
            "amount": 2_500_000,
            "sign_date": "2026-03-01",
        },
        raw_text=text,
        file_name="采购合同.pdf",
    )


def test_contract_decomposes_to_multiple_modules_without_human_input():
    decomposition = decompose_draft(_contract_classification(
        "采购合同 供货协议 约定增值税发票开具 甲方本公司 乙方供应商A 付款账期60天"
    ))

    module_keys = decomposition.module_keys()
    assert "contract_register" in module_keys
    assert "purchase" in module_keys
    assert "counterparty_ledger" not in module_keys
    assert decomposition.accounting_dimensions["cost"] is True
    assert decomposition.accounting_dimensions["contract"] is True
    assert decomposition.decomposition_source == "rules"
    assert decomposition.decomposition_version


def test_contract_with_sales_and_invoice_semantics_registers_multiple_dimensions():
    decomposition = decompose_draft(_contract_classification(
        "销售合同 客户订货 收入确认 开具增值税发票 回款条款 成本结转"
    ))

    assert decomposition.accounting_dimensions["revenue"] is True
    assert decomposition.accounting_dimensions["invoice"] is True
    assert "sales" in decomposition.module_keys()
    assert "tax_invoice" in decomposition.module_keys()


def test_risk_hints_extracted_for_large_amount_and_related_party():
    decomposition = decompose_draft(_contract_classification(
        "关联方采购合同 预付款30% 合同金额250万"
    ))

    risk_types = {item.risk_type for item in decomposition.risk_hints}
    assert "large_amount" in risk_types
    assert "related_party" in risk_types
    assert any(tag.startswith("dimension:") for tag in decomposition.semantic_tags)


def test_llm_enhancement_merges_without_dropping_rule_modules():
    class FakeLLM:
        def is_configured(self) -> bool:
            return True

        def chat(self, messages, temperature=0.1):
            return LLMResult(
                available=True,
                content=(
                    '{"primary_document_type":"contract",'
                    '"accounting_dimensions":{"bank_cash":true},'
                    '"module_targets":[{"module_key":"bank_cash_flow","confidence":0.8,"accounting_dimension":"bank_cash","reason":"LLM识别付款条款"}],'
                    '"semantic_tags":["llm:payment_terms"],'
                    '"risk_hints":[{"risk_type":"cutoff_risk","severity":"low","description":"期末前后签约","confidence":0.7}]}'
                ),
            )

    decomposition = decompose_draft(
        _contract_classification("采购合同 付款 银行转账"),
        llm_client=FakeLLM(),
    )

    assert decomposition.decomposition_source == "rules+llm"
    assert "purchase" in decomposition.module_keys()
    assert "bank_cash_flow" in decomposition.module_keys()
    assert "llm:payment_terms" in decomposition.semantic_tags
    assert any(item.risk_type == "cutoff_risk" for item in decomposition.risk_hints)
