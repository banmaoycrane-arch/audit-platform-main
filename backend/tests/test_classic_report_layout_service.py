"""经典报表布局：固定行次、零金额列示、合计末行对齐。"""
from decimal import Decimal

from app.services.accounting.classic_report_layout_service import (
    CLASSIC_CF_SPECS,
    CLASSIC_IS_TEMPLATE,
    build_classic_cash_flow_lines,
    build_classic_dual_column_balance_sheet,
    build_classic_income_statement_lines,
    classic_report_footer_rows,
    classic_report_header_rows,
)


def _sample_bs_lines() -> list[dict]:
    return [
        {"line_code": "cash_equivalents", "opening_balance": "1000.00", "closing_balance": "1500.00"},
        {"line_code": "assets_total", "opening_balance": "1000.00", "closing_balance": "1500.00"},
        {"line_code": "short_term_borrowings", "opening_balance": "200.00", "closing_balance": "300.00"},
        {"line_code": "liabilities_and_equity_total", "opening_balance": "1000.00", "closing_balance": "1500.00"},
    ]


def test_classic_income_statement_has_16_fixed_lines():
    lines = build_classic_income_statement_lines({}, {}, income_accounts={}, expense_accounts={})
    assert len(lines) == len(CLASSIC_IS_TEMPLATE) == 16
    assert all(line["current_amount"] == "0.00" for line in lines)
    assert all(line["year_to_date_amount"] == "0.00" for line in lines)


def test_classic_cash_flow_has_33_data_rows_plus_headers():
    lines = build_classic_cash_flow_lines([])
    header_count = sum(1 for spec in CLASSIC_CF_SPECS if spec.get("is_header"))
    data_count = len(CLASSIC_CF_SPECS) - header_count
    assert len(lines) == len(CLASSIC_CF_SPECS)
    data_lines = [line for line in lines if not line.get("is_header")]
    assert len(data_lines) == data_count
    assert all(line.get("current_amount") == "0.00" for line in data_lines if line.get("line_code") != "operating_header")


def test_classic_balance_sheet_grand_totals_align_on_last_row():
    layout = build_classic_dual_column_balance_sheet(_sample_bs_lines())
    paired = layout["paired_rows"]
    assert paired
    last = paired[-1]
    assert "资产总计" in last["asset_label"]
    assert "负债及所有者权益合计" in last["liability_label"]
    assert last["asset_closing"] == "1500.00"
    assert last["liability_closing"] == "1500.00"


def test_classic_header_footer_match_paper_layout():
    report = {"ledger_name": "测试单位", "as_of_date": "2026-03-31", "period_code": "2026-03"}
    header = classic_report_header_rows("balance_sheet", report)
    assert header[0] == ["资产负债表"]
    assert "编制单位：测试单位" in header[1][0]
    assert "编制日期：2026-03-31" in header[1][1]

    footer = classic_report_footer_rows({"signature": {"preparer_name": "张三", "approver_name": "李四", "reviewer_name": "王五"}})
    assert "制表人：张三" in footer[-1][0]
    assert "负责人：李四" in footer[-1][1]
    assert "复核：王五" in footer[-1][2]


def test_classic_cash_flow_fx_and_net_lines():
    lines = build_classic_cash_flow_lines(
        [{"line_code": "net_increase_in_cash", "current_amount": "88.00"}],
        fx_effect=Decimal("1.50"),
    )
    fx = next(line for line in lines if line.get("line_code") == "fx_effect_on_cash")
    net = next(line for line in lines if line.get("line_code") == "net_increase_in_cash")
    assert fx["current_amount"] == "1.50"
    assert net["current_amount"] == "88.00"
