"""功能模块台账登记测试。"""

from app.services.doc_parsing.import_routing_service import get_import_output_path
from app.services.basic_data.register_ingestion_service import (
    MODULE_DEFINITIONS,
    _detect_contract_modules,
    _normalize_document_type,
)


def test_ai_generated_output_path_is_register_ledger():
    assert get_import_output_path("ai_generated") == "register_ledger"


def test_module_definitions_map_business_modules():
    assert MODULE_DEFINITIONS["tax_invoice"]["module_path"] == "/tax/invoices"
    assert MODULE_DEFINITIONS["bank_cash_flow"]["module_path"] == "/bank/cash-flow-ledger"
    assert MODULE_DEFINITIONS["contract_register"]["module_path"] == "/audit/contracts"
    assert MODULE_DEFINITIONS["counterparty_ledger"]["module_path"] == "/basic/receivable-payable"
    assert MODULE_DEFINITIONS["purchase"]["module_path"] == "/inventory/purchase-in"
    assert MODULE_DEFINITIONS["sales"]["module_path"] == "/inventory/sale-out"


def test_purchase_contract_registers_contract_and_purchase_not_counterparty():
    modules = _detect_contract_modules(
        {
            "party_a": "甲方公司",
            "party_b": "供应商A",
            "contract_type": "purchase",
            "amount": 100000,
        },
        "采购合同 供货协议",
        "2026采购合同.pdf",
    )
    assert "contract_register" in modules
    assert "purchase" in modules
    assert "counterparty_ledger" not in modules


def test_sales_contract_registers_contract_and_sales_not_counterparty():
    modules = _detect_contract_modules(
        {
            "party_a": "本公司",
            "party_b": "客户B",
        },
        "销售合同 客户订货",
        "销售合同-客户B.pdf",
    )
    assert "contract_register" in modules
    assert "sales" in modules
    assert "counterparty_ledger" not in modules
    assert "purchase" not in modules


def test_normalize_document_type_aliases():
    assert _normalize_document_type("bank") == "bank_statement"
    assert _normalize_document_type("inventory") == "inventory_receipt"
