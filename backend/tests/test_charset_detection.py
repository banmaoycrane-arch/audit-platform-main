"""字符集检测与格式预检测单测。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.doc_parsing.charset_detection_service import (
    delimiter_label,
    detect_text_encoding,
    sniff_text_delimiter,
)
from app.services.doc_parsing.structured_format_detection_service import detect_structured_file_format
from tests.fixtures.day_book import write_daybook_csv


def test_detect_utf8_csv_encoding(tmp_path: Path) -> None:
    path = write_daybook_csv(tmp_path / "utf8.csv")
    info = detect_text_encoding(path)
    assert info["encoding"]
    assert "utf" in info["encoding"].lower()


def test_sniff_comma_delimiter(tmp_path: Path) -> None:
    path = write_daybook_csv(tmp_path / "comma.csv")
    assert sniff_text_delimiter(path) == ","
    assert delimiter_label(",") == "逗号"


def test_detect_structured_file_format_csv(tmp_path: Path) -> None:
    path = write_daybook_csv(tmp_path / "daybook.csv")
    result = detect_structured_file_format(str(path))
    assert result["is_structured_tabular"] is True
    assert result["parseable"] is True
    assert result["estimated_data_rows"] >= 1
    assert any("科目" in h or "凭证" in h for h in result["detected_headers"])


def test_detect_gbk_csv(tmp_path: Path) -> None:
    path = tmp_path / "gbk.csv"
    content = "科目代码,科目名称,借方,贷方\n1001,库存现金,100,0\n"
    path.write_bytes(content.encode("gbk"))
    info = detect_text_encoding(path)
    assert info.get("encoding")
    result = detect_structured_file_format(str(path))
    assert result["is_structured_tabular"] is True


def test_detect_format_with_manual_charset(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    path = tmp_path / "gb.csv"
    path.write_bytes("凭证号,摘要\n记-001,测试".encode("gbk"))
    with TestClient(app) as client:
        with path.open("rb") as handle:
            response = client.post(
                "/api/import-jobs/detect-format",
                files={"file": ("gb.csv", handle, "text/csv")},
                data={"charset": "gbk", "delimiter": "comma"},
            )
    assert response.status_code == 200
    payload = response.json()
    assert payload["charset"] == "gbk"
    assert payload["delimiter_label"] == "逗号"
