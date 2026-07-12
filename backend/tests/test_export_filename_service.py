from datetime import datetime, timezone
from decimal import Decimal

from app.db.models import ImportJob, Organization
from app.services.accounting.export_filename_service import build_import_job_export_filename


def test_build_import_job_export_filename_uses_ledger_timestamp_and_job_id():
    job = ImportJob(id=5, organization_id=1, ledger_id=2, status="completed")
    when = datetime(2026, 7, 10, 10, 3, 5, tzinfo=timezone.utc)
    filename = build_import_job_export_filename(
        job,
        ledger_name="星辰科技账簿",
        fmt="xlsx",
        exported_at=when,
    )
    assert filename == "星辰科技账簿_20260710_100305_job5_entries.xlsx"


def test_build_report_export_filename():
    from app.services.accounting.export_filename_service import build_report_export_filename

    when = datetime(2026, 7, 10, 19, 30, 5, tzinfo=timezone.utc)
    filename = build_report_export_filename(
        "balance_sheet",
        ledger_name="测试账套A",
        period_code="2026-01",
        fmt="xlsx",
        exported_at=when,
    )
    assert filename == "测试账套A_2026-01_资产负债表_20260710_193005.xlsx"
