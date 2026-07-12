"""现金流量表列报与直接/间接法勾稽测试。"""
from decimal import Decimal
from types import SimpleNamespace

from app.services.accounting.cash_flow_presentation_service import (
    build_direct_method_lines,
    build_indirect_method_lines,
    classify_voucher_cash_movements,
)


def _entry(code: str, debit: str = "0", credit: str = "0"):
    return SimpleNamespace(account_code=code, debit_amount=Decimal(debit), credit_amount=Decimal(credit))


def test_direct_revenue_to_bank_classified_as_sales_cash():
    """借银行贷收入：应归入销售商品收到的现金，而非误判为投资/筹资。"""
    voucher = [
        _entry("1002", debit="5000"),
        _entry("6001", credit="5000"),
    ]
    amounts, flags = classify_voucher_cash_movements(voucher)
    assert flags["direct_revenue_to_bank"] is True
    assert amounts["sales_cash_received"] == Decimal("5000")


def test_receivable_collection_classified_as_sales_cash():
    """借银行贷应收：应收后回款路径。"""
    voucher = [
        _entry("1002", debit="3000"),
        _entry("1122", credit="3000"),
    ]
    amounts, flags = classify_voucher_cash_movements(voucher)
    assert flags["receivable_collection"] is True
    assert amounts["sales_cash_received"] == Decimal("3000")


def test_cost_payment_classified_as_goods_services_paid():
    voucher = [
        _entry("6401", debit="2000"),
        _entry("1002", credit="2000"),
    ]
    amounts, _ = classify_voucher_cash_movements(voucher)
    assert amounts["goods_services_cash_paid"] == Decimal("2000")


def test_internal_cash_transfer_skipped():
    voucher = [
        _entry("1001", debit="1000"),
        _entry("1002", credit="1000"),
    ]
    amounts, flags = classify_voucher_cash_movements(voucher)
    assert amounts["sales_cash_received"] == Decimal("0")
    assert flags["internal_transfer_skipped"] == Decimal("1000")


def test_build_direct_method_net_equals_inflow_minus_outflow():
    groups = {
        1: [_entry("1002", debit="5000"), _entry("6001", credit="5000")],
        2: [_entry("6401", debit="3000"), _entry("1002", credit="3000")],
    }
    lines, totals, _ = build_direct_method_lines(groups)
    assert totals["operating_net"] == Decimal("2000")
    assert totals["net_increase_in_cash"] == Decimal("2000")
    net_line = next(l for l in lines if l["line_code"] == "operating_net")
    assert net_line["current_amount"] == "2000.00"


def test_indirect_method_reconciles_with_direct_when_no_working_capital_change():
    balance_rows = [
        {
            "account_code": "1122",
            "category": "asset",
            "opening_debit": "0",
            "opening_credit": "0",
            "closing_debit": "0",
            "closing_credit": "0",
            "period_credit": "0",
        },
    ]
    indirect = build_indirect_method_lines(Decimal("2000"), balance_rows, Decimal("2000"))
    tail = indirect[-1]
    assert tail["reconciled_with_direct"] is True
    assert tail["current_amount"] == "2000.00"
