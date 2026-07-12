"""凭证号识别：凭证字+凭证号分列、序时簿续行、格式变化。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.doc_parsing.file_parser_service import parse_structured_accounting_entries
from app.services.doc_parsing.voucher_no_resolution import (
    compose_voucher_no,
    resolve_voucher_no_from_parts,
)
from tests.fixtures.day_book import write_voucher_serpentine_xlsx


def test_compose_voucher_type_and_serial() -> None:
    assert compose_voucher_no("记", "1") == "记-1"
    assert compose_voucher_no("记", "001") == "记-001"
    assert compose_voucher_no("", "记-0002") == "记-0002"


def test_resolve_voucher_serial_changes_start_new_voucher() -> None:
    _, _, serial1, composed1 = resolve_voucher_no_from_parts(
        raw_voucher_no="1",
        raw_voucher_type="记",
        last_type="",
        last_serial="",
        last_composed="",
    )
    assert composed1 == "记-1"

    _, _, serial2, composed2 = resolve_voucher_no_from_parts(
        raw_voucher_no="",
        raw_voucher_type="记",
        last_type="记",
        last_serial=serial1,
        last_composed=composed1,
    )
    assert composed2 == "记-1"

    _, _, serial3, composed3 = resolve_voucher_no_from_parts(
        raw_voucher_no="2",
        raw_voucher_type="记",
        last_type="记",
        last_serial=serial2,
        last_composed=composed2,
    )
    assert composed3 == "记-2"
    assert serial3 == "2"


def test_kingdee_split_columns_do_not_collapse_to_voucher_type(tmp_path: Path) -> None:
    rows = [
        ["凭证号", "凭证字", "日期", "摘要", "科目名称", "借方", "贷方"],
        ["1", "记", "2026-01-01", "a", "银行存款", 100, 0],
        ["", "记", "2026-01-01", "b", "应收账款", 0, 100],
        ["2", "记", "2026-01-02", "c", "银行存款", 200, 0],
        ["", "记", "2026-01-02", "d", "应付账款", 0, 200],
    ]
    path = tmp_path / "kingdee_split.xlsx"
    pd.DataFrame(rows).to_excel(path, index=False, header=False)
    result = parse_structured_accounting_entries(str(path))
    voucher_nos = [entry["voucher_no"] for entry in result.entries]
    assert voucher_nos == ["记-1", "记-1", "记-2", "记-2"]


def test_voucher_serpentine_still_groups_correctly(tmp_path: Path) -> None:
    path = write_voucher_serpentine_xlsx(tmp_path / "serpentine.xlsx")
    result = parse_structured_accounting_entries(str(path))
    assert len(result.entries) == 6
    assert result.entries[0]["voucher_no"] == "记-0001"
    assert result.entries[1]["voucher_no"] == "记-0001"
    assert result.entries[4]["voucher_no"] == "记-0002"
