"""财务报表落盘交付：生成标准格式文件并输出邮递目录路径。"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod
from app.models.ledger import Ledger
from app.services.accounting import financial_statements_service
from app.services.accounting.export_filename_service import (
    build_reports_package_filename,
    slugify_filename_part,
)
from app.services.accounting.report_export_service import (
    EXPORT_BUILDERS,
    REPORT_PDF_FILENAMES,
    REPORT_XLSX_FILENAMES,
    SUBSIDIARY_XLSX_FILENAME,
    build_reports_zip_package,
)
from app.services.accounting.report_pdf_service import PDF_BUILDERS, ReportSignature
from app.services.accounting.subsidiary_ledger_service import export_subsidiary_ledger_xlsx


def get_delivery_root() -> Path:
    """审计/军工审查报表交付根目录（可通过环境变量覆盖）。"""
    env = os.environ.get("REPORT_DELIVERY_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    # audit-platform-main/exports/audit-delivery
    return (Path(__file__).resolve().parents[3] / "exports" / "audit-delivery").resolve()


def _delivery_folder_name(ledger_name: str | None, period_code: str | None) -> str:
    ledger_slug = slugify_filename_part(ledger_name or "", fallback="ledger")
    period_slug = slugify_filename_part(period_code or "", fallback="period", max_len=16)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{ledger_slug}_{period_slug}_{timestamp}"


def deliver_reports_package(
    db: Session,
    *,
    ledger_id: int,
    period_id: int,
    as_of_date: date | None = None,
    include_pdf: bool = True,
    include_subsidiary: bool = True,
    preparer_name: str | None = None,
    reviewer_name: str | None = None,
    approver_name: str | None = None,
) -> dict[str, Any]:
    """
    生成标准格式财务报表并落盘到交付目录，返回邮递路径与文件清单。
    """
    ledger = db.get(Ledger, ledger_id)
    period = db.get(AccountingPeriod, period_id)
    if not ledger:
        raise LookupError("账簿不存在")
    if not period:
        raise LookupError("会计期间不存在")

    ledger_name = ledger.name
    period_code = period.period_code

    trial = financial_statements_service.trial_balance_report(db, ledger_id, period_id, as_of_date=as_of_date)
    balance = financial_statements_service.balance_sheet(db, ledger_id, period_id, as_of_date=as_of_date)
    income = financial_statements_service.income_statement(db, ledger_id, period_id)
    cash_flow = financial_statements_service.cash_flow_statement(db, ledger_id, period_id)

    signature = ReportSignature.from_params(
        preparer_name=preparer_name,
        reviewer_name=reviewer_name,
        approver_name=approver_name,
    )

    root = get_delivery_root()
    folder_name = _delivery_folder_name(ledger_name, period_code)
    target_dir = root / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[str] = []
    zip_entries: list[tuple[str, bytes]] = []

    for kind, report in [
        ("trial_balance", trial),
        ("balance_sheet", balance),
        ("income_statement", income),
        ("cash_flow", cash_flow),
    ]:
        xlsx_name = REPORT_XLSX_FILENAMES[kind]
        xlsx_body = EXPORT_BUILDERS[kind]["xlsx"](report, ledger_name=ledger_name)
        xlsx_path = target_dir / xlsx_name
        xlsx_path.write_bytes(xlsx_body)
        written_files.append(str(xlsx_path))
        zip_entries.append((xlsx_name, xlsx_body))

        if include_pdf:
            pdf_builder = PDF_BUILDERS[kind]
            if kind in {"income_statement", "cash_flow"}:
                pdf_body = pdf_builder(report, signature, period_code=period_code, ledger_name=ledger_name)
            else:
                pdf_body = pdf_builder(report, signature, ledger_name=ledger_name)
            pdf_name = REPORT_PDF_FILENAMES[kind]
            pdf_path = target_dir / pdf_name
            pdf_path.write_bytes(pdf_body)
            written_files.append(str(pdf_path))
            zip_entries.append((pdf_name, pdf_body))

    if include_subsidiary:
        subsidiary_body = export_subsidiary_ledger_xlsx(
            db,
            ledger_id=ledger_id,
            period_id=period_id,
            date_from=period.start_date,
            date_to=as_of_date or period.end_date,
            ledger_name=ledger_name,
            period_code=period_code,
        )
        subsidiary_path = target_dir / SUBSIDIARY_XLSX_FILENAME
        subsidiary_path.write_bytes(subsidiary_body)
        written_files.append(str(subsidiary_path))
        zip_entries.append((SUBSIDIARY_XLSX_FILENAME, subsidiary_body))

    zip_name = build_reports_package_filename(ledger_name=ledger_name, period_code=period_code)
    zip_body = build_reports_zip_package(zip_entries)
    zip_path = target_dir / zip_name
    zip_path.write_bytes(zip_body)
    written_files.append(str(zip_path))

    manifest_lines = [
        "财务报表交付清单",
        f"编制单位：{ledger_name}",
        f"会计期间：{period_code}",
        f"交付目录：{target_dir}",
        f"生成时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "文件列表：",
    ]
    for path in written_files:
        manifest_lines.append(f"  - {path}")
    manifest_lines.extend([
        "",
        "格式说明：",
        "  - 科目余额表/总账：期初借方余额、本期借方发生额、本年借方累计、期末借方余额等标准十列",
        "  - 明细账：日期、凭证字号、摘要、借方金额、贷方金额、方向、余额",
        "  - 利润表/现金流量表：行次 + 项目 + 本期金额",
        "  - 资产负债表：行次 + 报表项目 + 期末余额",
    ])
    manifest_path = target_dir / "00_交付清单.txt"
    manifest_path.write_text("\n".join(manifest_lines), encoding="utf-8")
    written_files.insert(0, str(manifest_path))

    return {
        "delivery_root": str(root),
        "delivery_folder": str(target_dir),
        "manifest_path": str(manifest_path),
        "zip_path": str(zip_path),
        "files": written_files,
        "ledger_name": ledger_name,
        "period_code": period_code,
    }
