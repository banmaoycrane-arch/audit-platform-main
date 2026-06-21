"""序时簿期间识别与导入路由测试。"""

from datetime import date

from app.services.import_routing_service import (
    get_import_output_path,
    is_day_book_source_type,
    should_persist_structured_entries,
)
from app.services.period_detection_service import (
    build_month_period_suggestion,
    detect_dominant_month,
)


def test_import_output_path_is_stable_by_source_type():
    assert get_import_output_path("ledger_day_book") == "direct_entries"
    assert get_import_output_path("audit_day_book") == "direct_entries"
    assert get_import_output_path("ai_generated") == "ai_draft"
    assert get_import_output_path("manual_entry") == "direct_entries"


def test_structured_entries_not_persisted_for_ai_generated():
    assert should_persist_structured_entries("ai_generated") is False
    assert should_persist_structured_entries("ledger_day_book") is True


def test_is_day_book_source_type():
    assert is_day_book_source_type("ledger_day_book") is True
    assert is_day_book_source_type("audit_day_book") is True
    assert is_day_book_source_type("ai_generated") is False


def test_detect_dominant_month_from_voucher_dates():
    dominant = detect_dominant_month(
        [
            "2026-01-03",
            "2026-01-05",
            "2026-02-01",
            date(2026, 1, 10),
        ]
    )
    assert dominant == date(2026, 1, 1)


def test_build_month_period_suggestion():
    suggestion = build_month_period_suggestion(date(2026, 3, 15))
    assert suggestion["period_code"] == "2026-03"
    assert suggestion["start_date"] == "2026-03-01"
    assert suggestion["end_date"] == "2026-03-31"
