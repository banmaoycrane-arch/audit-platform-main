"""序时簿表区域识别（day_book_parser）回归测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.doc_parsing.day_book_parser import (
    HEADER_SCAN_MAX_ROWS,
    extract_table_metadata,
    forward_fill_merged_row_values,
    resolve_structured_table,
)
from app.services.doc_parsing.file_parser_service import parse_structured_accounting_entries
from app.services.doc_parsing.parser_engine.rule_parsers import parse_accounting_entry_rules
from tests.fixtures.day_book import (
    write_daybook_csv,
    write_daybook_xlsx,
    write_merged_title_xlsx,
    write_voucher_serpentine_tsv,
    write_voucher_serpentine_xlsx,
)


@pytest.fixture
def preamble_csv(tmp_path: Path) -> Path:
    return write_daybook_csv(tmp_path / "daybook_preamble.csv")


@pytest.fixture
def preamble_xlsx(tmp_path: Path) -> Path:
    return write_daybook_xlsx(tmp_path / "daybook_preamble.xlsx")


@pytest.fixture
def merged_title_xlsx(tmp_path: Path) -> Path:
    return write_merged_title_xlsx(tmp_path / "daybook_merged_title.xlsx")


class TestDayBookParser:
    def test_header_scan_max_rows_is_25(self) -> None:
        assert HEADER_SCAN_MAX_ROWS == 25

    def test_detect_header_after_five_preamble_rows_csv(self, preamble_csv: Path) -> None:
        layout = resolve_structured_table(str(preamble_csv))
        assert layout is not None
        assert layout.header_row_index == 5
        assert layout.metadata.company_name is not None
        assert "示例科技" in layout.metadata.company_name
        assert layout.metadata.report_period is not None
        assert "2026" in layout.metadata.report_period

    def test_data_zone_excludes_footer_total_and_signature(self, preamble_csv: Path) -> None:
        layout = resolve_structured_table(str(preamble_csv))
        assert layout is not None
        assert len(layout.data_frame) == 2

    def test_forward_fill_merged_title_row(self, merged_title_xlsx: Path) -> None:
        import pandas as pd

        raw = pd.read_excel(merged_title_xlsx, header=None, dtype=str)
        filled = forward_fill_merged_row_values(raw)
        first_row = [str(v) for v in filled.iloc[0].values if str(v) != "nan" and str(v).strip()]
        assert first_row.count("序时账") >= 1

    def test_parse_structured_entries_csv_with_preamble(self, preamble_csv: Path) -> None:
        result = parse_structured_accounting_entries(str(preamble_csv))
        assert len(result.entries) == 2
        assert result.success_rows == 2

    def test_parse_structured_entries_xlsx_with_preamble(self, preamble_xlsx: Path) -> None:
        result = parse_structured_accounting_entries(str(preamble_xlsx))
        assert len(result.entries) == 2

    def test_rule_engine_fallback_with_preamble(self, preamble_csv: Path) -> None:
        rule_data = parse_accounting_entry_rules("", file_path=str(preamble_csv))
        assert rule_data["entry_count"] == 2
        assert rule_data["company_name"] is not None
        assert len(rule_data["columns"]) >= 6

    def test_metadata_title_extracted(self, preamble_xlsx: Path) -> None:
        layout = resolve_structured_table(str(preamble_xlsx))
        assert layout is not None
        meta = extract_table_metadata(layout.raw_frame, layout.header_row_index)
        assert meta.title is not None
        assert "序时" in meta.title

    def test_detect_header_deep_preamble(self, tmp_path: Path) -> None:
        """表头在第 8 行（0-indexed），仍在 25 行扫描窗口内。"""
        import pandas as pd

        rows: list[list[str]] = []
        for i in range(7):
            rows.append([f"说明行{i + 1}"])
        rows.append(["凭证号", "日期", "摘要", "科目", "借方", "贷方"])
        rows.append(["记-1", "2026-01-01", "测试", "1002", "100", "0"])
        path = tmp_path / "deep_preamble.csv"
        pd.DataFrame(rows).to_csv(path, index=False, header=False)
        layout = resolve_structured_table(str(path))
        assert layout is not None
        assert layout.header_row_index == 7
        assert len(layout.data_frame) == 1

    def test_voucher_serpentine_xlsx(self, tmp_path: Path) -> None:
        path = write_voucher_serpentine_xlsx(tmp_path / "voucher_serpentine.xlsx")
        layout = resolve_structured_table(str(path))
        assert layout is not None
        assert layout.header_row_index == 3
        assert layout.metadata.title is not None

        result = parse_structured_accounting_entries(str(path))
        assert len(result.entries) == 6
        assert result.entries[0]["account_code"] == "100202"
        assert result.entries[1]["voucher_no"] == "记-0001"
        assert result.entries[4]["debit_amount"] > 0

    def test_voucher_serpentine_tab_csv(self, tmp_path: Path) -> None:
        path = write_voucher_serpentine_tsv(tmp_path / "voucher_serpentine.csv")
        result = parse_structured_accounting_entries(str(path))
        assert len(result.entries) == 6

        rule_data = parse_accounting_entry_rules("", file_path=str(path))
        assert rule_data["entry_count"] == 6
