"""序时簿续行解析与检测报告分组。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from app.services.audit.audit_day_book_service import _build_day_book_report
from app.services.doc_parsing.file_parser_service import parse_structured_accounting_entries
from tests.fixtures.day_book import write_voucher_serpentine_xlsx


def test_time_column_forward_fill_and_balanced_report(tmp_path: Path) -> None:
    rows = [
        ["时间", "编号", "摘要", "科目", "借方", "贷方"],
        ["2022-06-30", "7", "利息", "6603 财务费用", "2111.04", ""],
        ["", "", "银行存款", "1002 银行存款", "", "2111.04"],
        ["2022-07-01", "8", "采购", "1403 原材料", "500.00", ""],
        ["", "", "应付账款", "2202 应付账款", "", "500.00"],
    ]
    path = tmp_path / "time_column.xlsx"
    pd.DataFrame(rows).to_excel(path, index=False, header=False)
    result = parse_structured_accounting_entries(str(path))
    assert len(result.entries) == 4
    assert result.entries[0]["voucher_no"] == "7"
    assert result.entries[1]["voucher_no"] == "7"
    assert result.entries[1]["voucher_date"] == date(2022, 6, 30)
    assert result.entries[1]["entry_line_no"] == 2
    assert result.entries[2]["voucher_no"] == "8"

    report = _build_day_book_report(result.entries)
    assert report.unbalanced_count == 0


def test_same_voucher_no_different_dates_not_merged_in_report(tmp_path: Path) -> None:
    rows = [
        ["凭证日期", "凭证号", "摘要", "科目", "借方", "贷方"],
        ["2022-06-30", "记-7", "a", "1001", "100", ""],
        ["2022-07-01", "记-7", "b", "1002", "", "100"],
    ]
    path = tmp_path / "same_no_diff_date.xlsx"
    pd.DataFrame(rows).to_excel(path, index=False, header=False)
    result = parse_structured_accounting_entries(str(path))
    report = _build_day_book_report(result.entries)
    assert report.total_vouchers == 2
    assert report.total_entries == 2
    assert {item.voucher_date for item in report.unbalanced_vouchers} == {"2022-06-30", "2022-07-01"}


def test_serpentine_fixture_groups_by_voucher(tmp_path: Path) -> None:
    path = write_voucher_serpentine_xlsx(tmp_path / "serpentine.xlsx")
    result = parse_structured_accounting_entries(str(path))
    report = _build_day_book_report(result.entries)
    assert report.total_vouchers >= 2
    assert result.entries[1]["voucher_no"] == "记-0001"
    assert result.entries[1]["entry_line_no"] == 2
