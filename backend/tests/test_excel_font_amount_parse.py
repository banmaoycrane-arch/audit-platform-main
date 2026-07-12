"""Excel 蓝字/红字（会计冲减）金额解析测试。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from app.services.audit.audit_day_book_service import _build_day_book_report
from app.services.doc_parsing.excel_font_amount_service import (
    classify_font_color,
    infer_debit_credit_from_colored_row,
    signed_amount_from_cell,
)
from app.services.doc_parsing.file_parser_service import parse_structured_accounting_entries


def test_classify_blue_and_red_font() -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet["A1"] = 100
    worksheet["A1"].font = Font(color="0000FF")
    worksheet["A2"] = 200
    worksheet["A2"].font = Font(color="FF0000")
    assert classify_font_color(worksheet["A1"]) == "blue"
    assert classify_font_color(worksheet["A2"]) == "red"


def test_signed_amount_from_cell() -> None:
    assert signed_amount_from_cell(1000, "blue", side="debit") == Decimal("1000.00")
    assert signed_amount_from_cell(1000, "red", side="debit") == Decimal("-1000.00")
    assert signed_amount_from_cell(1000, "red", side="credit", summary="正常来账") == Decimal("1000.00")
    assert signed_amount_from_cell(1000, "red", side="credit", summary="贷方冲红") == Decimal("-1000.00")
    assert signed_amount_from_cell(-500, "default", side="debit") == Decimal("-500.00")


def test_red_in_debit_column_is_negative_debit_not_credit() -> None:
    debit, credit, used = infer_debit_credit_from_colored_row(
        row_values=[None, None, None, None, 500, None],
        headers=["凭证号", "日期", "摘要", "科目", "借方", "贷方"],
        excel_row_index=10,
        color_grid={(10, 4): "red"},
        has_debit_column=True,
        has_credit_column=True,
    )
    assert used is True
    assert debit == Decimal("-500.00")
    assert credit == Decimal("0.00")


def test_blue_debit_and_red_debit_reversal_balance(tmp_path: Path) -> None:
    path = tmp_path / "blue_red_reversal.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    rows = [
        ["凭证号", "日期", "摘要", "科目", "借方", "贷方"],
        ["记-1", "2026-01-01", "原记", "5001", 1000, None],
        ["", "", "借方冲红", "5001", 1000, None],
        ["", "", "原贷", "1002", None, 1000],
        ["", "", "贷方冲红", "1002", None, -1000],
    ]
    for row in rows:
        worksheet.append(row)
    worksheet["E2"].font = Font(color="0000FF")
    worksheet["E3"].font = Font(color="FF0000")
    worksheet["F4"].font = Font(color="0000FF")
    worksheet["F5"].font = Font(color="FF0000")
    workbook.save(path)

    result = parse_structured_accounting_entries(str(path))
    assert len(result.entries) == 4
    assert result.entries[0]["debit_amount"] == Decimal("1000.00")
    assert result.entries[1]["debit_amount"] == Decimal("-1000.00")
    assert result.entries[2]["credit_amount"] == Decimal("1000.00")
    assert result.entries[3]["credit_amount"] == Decimal("-1000.00")

    report = _build_day_book_report(result.entries)
    assert report.unbalanced_count == 0


def test_negative_numeric_in_credit_column_is_red_reversal() -> None:
    debit, credit, used = infer_debit_credit_from_colored_row(
        row_values=[None, None, "贷方冲红", None, None, -800],
        headers=["凭证号", "日期", "摘要", "科目", "借方", "贷方"],
        excel_row_index=3,
        color_grid={},
        has_debit_column=True,
        has_credit_column=True,
    )
    assert used is False
    assert debit == Decimal("0.00")
    assert credit == Decimal("-800.00")


def test_red_reversal_on_credit_column_with_summary() -> None:
    debit, credit, used = infer_debit_credit_from_colored_row(
        row_values=[None, None, "贷方冲红", None, None, 800],
        headers=["凭证号", "日期", "摘要", "科目", "借方", "贷方"],
        excel_row_index=3,
        color_grid={(3, 5): "red"},
        has_debit_column=True,
        has_credit_column=True,
    )
    assert used is True
    assert debit == Decimal("0.00")
    assert credit == Decimal("-800.00")
