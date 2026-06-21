"""功能模块台账登记测试。"""

from app.services.import_routing_service import get_import_output_path
from app.services.register_ingestion_service import (
    MODULE_DEFINITIONS,
    _detect_contract_modules,
    _normalize_document_type,
)


def test_ai_generated_output_path_is_register_ledger():
    assert get_import_output_path("ai_generated") == "register_ledger"


def test_module_definitions_map_business_modules():
    assert MODULE_DEFINITIONS["tax_invoice"]["module_path"] == "/tax/invoices"
    assert MODULE_DEFINITIONS["bank_cash_flow"]["module_path"] == "/bank/cash-flow-ledger"
    assert MODULE_DEFINITIONS["counterparty_ledger"]["module_path"] == "/basic/counterparties"
    assert MODULE_DEFINITIONS["purchase"]["module_path"] == "/inventory/purchase-in"
    assert MODULE_DEFINITIONS["sales"]["module_path"] == "/inventory/sale-out"


def test_purchase_contract_registers_multiple_modules():
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
    assert "counterparty_ledger" in modules
    assert "purchase" in modules


def test_sales_contract_registers_counterparty_and_sales():
    modules = _detect_contract_modules(
        {
            "party_a": "本公司",
            "party_b": "客户B",
        },
        "销售合同 客户订货",
        "销售合同-客户B.pdf",
    )
    assert "counterparty_ledger" in modules
    assert "sales" in modules
    assert "purchase" not in modules


def test_normalize_document_type_aliases():
    assert _normalize_document_type("bank") == "bank_statement"
    assert _normalize_document_type("inventory") == "inventory_receipt"
