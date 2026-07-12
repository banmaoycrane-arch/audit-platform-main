"""导出文件命名：账套 + 时间戳 + 任务序号，便于归档识别。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import ImportJob

_FILENAME_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

_REPORT_KIND_LABEL = {
    "trial_balance": "科目余额表",
    "balance_sheet": "资产负债表",
    "income_statement": "利润表",
    "cash_flow": "现金流量表",
    "package": "财务报表包",
    "subsidiary_ledger": "明细账",
}


def slugify_filename_part(value: str, *, max_len: int = 48, fallback: str = "ledger") -> str:
    """将账套名等文本转为安全文件名片段（保留中文）。"""
    normalized = (value or "").strip()
    if not normalized:
        return fallback
    cleaned = _FILENAME_UNSAFE.sub("_", normalized)
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned.strip("._")
    if not cleaned:
        return fallback
    return cleaned[:max_len]


def build_import_job_export_filename(
    job: ImportJob,
    *,
    ledger_name: str | None,
    fmt: str,
    exported_at: datetime | None = None,
) -> str:
    """
    命名规则：{账套}_{YYYYMMDD_HHMMSS}_job{任务ID}_entries.{格式}
    示例：星辰科技账簿_20260710_180305_job5_entries.xlsx
    """
    when = exported_at or datetime.now(timezone.utc)
    timestamp = when.strftime("%Y%m%d_%H%M%S")
    ledger_slug = slugify_filename_part(ledger_name or "", fallback="ledger")
    ext = fmt.lower().lstrip(".")
    return f"{ledger_slug}_{timestamp}_job{job.id}_entries.{ext}"


def build_report_export_filename(
    report_kind: str,
    *,
    ledger_name: str | None,
    period_code: str | None,
    fmt: str,
    exported_at: datetime | None = None,
) -> str:
    """
    命名规则：{账套}_{期间}_{报表名}_{YYYYMMDD_HHMMSS}.{格式}
    示例：测试账簿_2026-01_科目余额表_20260710_193000.xlsx
    """
    when = exported_at or datetime.now(timezone.utc)
    timestamp = when.strftime("%Y%m%d_%H%M%S")
    ledger_slug = slugify_filename_part(ledger_name or "", fallback="ledger")
    period_slug = slugify_filename_part(period_code or "", fallback="period", max_len=16)
    label = _REPORT_KIND_LABEL.get(report_kind, report_kind)
    report_slug = slugify_filename_part(label, fallback=report_kind, max_len=24)
    ext = fmt.lower().lstrip(".")
    return f"{ledger_slug}_{period_slug}_{report_slug}_{timestamp}.{ext}"


def build_reports_package_filename(
    *,
    ledger_name: str | None,
    period_code: str | None,
    exported_at: datetime | None = None,
) -> str:
    """命名规则：{账套}_{期间}_财务报表包_{时间戳}.zip"""
    when = exported_at or datetime.now(timezone.utc)
    timestamp = when.strftime("%Y%m%d_%H%M%S")
    ledger_slug = slugify_filename_part(ledger_name or "", fallback="ledger")
    period_slug = slugify_filename_part(period_code or "", fallback="period", max_len=16)
    return f"{ledger_slug}_{period_slug}_财务报表包_{timestamp}.zip"


def content_disposition_attachment(filename: str) -> str:
    """生成兼容中文文件名的 Content-Disposition。"""
    from urllib.parse import quote

    ext = filename.rsplit(".", 1)[-1] if "." in filename else "dat"
    job_match = re.search(r"job(\d+)_entries", filename)
    ascii_fallback = f"ledger_{job_match.group(1) if job_match else 'export'}_entries.{ext}"
    if not job_match:
        ascii_fallback = f"report_export.{ext}"
    encoded = quote(filename)
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"
