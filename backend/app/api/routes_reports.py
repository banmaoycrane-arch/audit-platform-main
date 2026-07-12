# -*- coding: utf-8 -*-
from datetime import date
from typing import Any
"""
模块功能：三大财务报表 API 路由（科目余额表、资产负债表、利润表）
业务场景：财务核算完成后向用户呈现三大基础报表
政策依据：企业会计准则关于报表列报的基本原则
输入数据：组织 ID、期间 ID
输出结果：三大报表的 JSON 数据
创建日期：2026-06-25
更新记录：
    2026-06-25  增加统一异常捕获，返回业务语义化的错误信息
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod
from app.db.session import get_db
from app.models.ledger import Ledger
from app.services.accounting import financial_statements_service
from app.services.accounting.export_filename_service import (
    build_report_export_filename,
    build_reports_package_filename,
    content_disposition_attachment,
)
from app.services.accounting.report_export_service import (
    CONTENT_TYPES,
    EXPORT_BUILDERS,
    REPORT_PDF_FILENAMES,
    REPORT_XLSX_FILENAMES,
    build_reports_zip_package,
    SUPPORTED_FORMATS,
)
from app.services.accounting.report_pdf_service import PDF_BUILDERS, ReportSignature

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _check_period(db: Session, period_id: int) -> None:
    """校验会计期间是否存在，不存在则抛出 404 异常。"""
    if not db.get(AccountingPeriod, period_id):
        raise HTTPException(status_code=404, detail="会计期间不存在")


def _run_report(
    report_func: Any,
    db: Session,
    ledger_id: int,
    period_id: int,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """
    功能描述：统一调用报表服务并捕获业务异常
    业务逻辑：将 LookupError 映射为 404，ValueError 映射为 400，SQLAlchemyError 映射为 422

    Args:
        report_func: 报表计算函数
        db: 数据库会话
        ledger_id: 账簿 ID
        period_id: 期间 ID

    Returns:
        dict: 报表数据
    """
    try:
        result = report_func(db, ledger_id, period_id, as_of_date=as_of_date)
        return result if isinstance(result, dict) else {}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=422, detail=f"报表数据加载失败，请检查科目表或分录表结构：{exc}")


@router.get("/trial-balance")
def trial_balance(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    as_of_date: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """科目余额表：返回各科目期初/本期/期末借贷六列及借贷合计。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    return _run_report(
        financial_statements_service.trial_balance_report,
        db,
        effective_ledger_id,
        period_id,
        as_of_date,
    )


@router.get("/balance-sheet")
def balance_sheet(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    as_of_date: date | None = None,
    presentation_mode: str = "balance",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """资产负债表：返回资产/负债/权益分组、恒等式校验与重分类调整记录。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    return _run_report(
        lambda db, lid, pid, as_of_date=None: financial_statements_service.balance_sheet(
            db,
            lid,
            pid,
            as_of_date=as_of_date,
            presentation_mode=presentation_mode,
        ),
        db,
        effective_ledger_id,
        period_id,
        as_of_date,
    )


@router.get("/balance-sheet/breakdown")
def balance_sheet_breakdown(
    period_id: int,
    account_prefix: str,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    category: str | None = None,
    as_of_date: date | None = None,
    presentation_mode: str = "balance",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """资产负债表下钻：返回某汇总科目下按明细编码拆分的余额。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    return _run_report(
        lambda db, lid, pid, as_of_date=None: financial_statements_service.account_balance_breakdown(
            db,
            lid,
            pid,
            account_prefix,
            category=category,
            as_of_date=as_of_date,
            presentation_mode=presentation_mode,
        ),
        db,
        effective_ledger_id,
        period_id,
        as_of_date,
    )


@router.get("/income-statement")
def income_statement(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """利润表：返回收入、成本、期间费用、营业利润、利润总额、净利润。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    return _run_report(
        financial_statements_service.income_statement,
        db,
        effective_ledger_id,
        period_id,
    )


def _export_report_response(
    report_kind: str,
    report: dict[str, Any],
    *,
    ledger_name: str | None,
    period_code: str | None,
    fmt: str,
    signature: ReportSignature | None = None,
) -> StreamingResponse:
    if fmt not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail=f"不支持的导出格式: {fmt}")
    sig = signature or ReportSignature()
    payload = dict(report)
    if sig.preparer_name or sig.reviewer_name or sig.approver_name:
        payload["signature"] = {
            "preparer_name": sig.preparer_name,
            "reviewer_name": sig.reviewer_name,
            "approver_name": sig.approver_name,
        }
    if fmt == "pdf":
        pdf_builder = PDF_BUILDERS.get(report_kind)
        if not pdf_builder:
            raise HTTPException(status_code=400, detail=f"不支持的 PDF 报表类型: {report_kind}")
        if report_kind in {"income_statement", "cash_flow"}:
            body = pdf_builder(payload, sig, period_code=period_code or payload.get("period_code"), ledger_name=ledger_name)
        else:
            body = pdf_builder(payload, sig, ledger_name=ledger_name)
        filename = build_report_export_filename(
            report_kind,
            ledger_name=ledger_name,
            period_code=period_code,
            fmt="pdf",
        )
        return StreamingResponse(
            iter([body]),
            media_type=CONTENT_TYPES["pdf"],
            headers={"Content-Disposition": content_disposition_attachment(filename)},
        )
    builder = EXPORT_BUILDERS.get(report_kind, {}).get(fmt)
    if not builder:
        raise HTTPException(status_code=400, detail=f"不支持的报表类型: {report_kind}")
    body = builder(payload, ledger_name=ledger_name)
    filename = build_report_export_filename(
        report_kind,
        ledger_name=ledger_name,
        period_code=period_code or report.get("period_code"),
        fmt=fmt,
    )
    return StreamingResponse(
        iter([body]),
        media_type=CONTENT_TYPES[fmt],
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )


def _ledger_and_period_meta(db: Session, ledger_id: int, period_id: int) -> tuple[str | None, str | None]:
    ledger = db.get(Ledger, ledger_id)
    period = db.get(AccountingPeriod, period_id)
    return (ledger.name if ledger else None, period.period_code if period else None)


@router.get("/trial-balance/export")
def export_trial_balance(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    as_of_date: date | None = None,
    format: str = "xlsx",
    preparer_name: str | None = None,
    reviewer_name: str | None = None,
    approver_name: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出科目余额表（xlsx / csv / pdf 签章版）。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    report = _run_report(
        financial_statements_service.trial_balance_report,
        db,
        effective_ledger_id,
        period_id,
        as_of_date,
    )
    ledger_name, period_code = _ledger_and_period_meta(db, effective_ledger_id, period_id)
    signature = ReportSignature.from_params(
        preparer_name=preparer_name,
        reviewer_name=reviewer_name,
        approver_name=approver_name,
    )
    return _export_report_response(
        "trial_balance",
        report,
        ledger_name=ledger_name,
        period_code=period_code or report.get("period_code"),
        fmt=format.lower(),
        signature=signature,
    )


@router.get("/balance-sheet/export")
def export_balance_sheet(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    as_of_date: date | None = None,
    presentation_mode: str = "balance",
    format: str = "xlsx",
    preparer_name: str | None = None,
    reviewer_name: str | None = None,
    approver_name: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出资产负债表（xlsx / csv / pdf 签章版）。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    report = _run_report(
        lambda db, lid, pid, as_of_date=None: financial_statements_service.balance_sheet(
            db,
            lid,
            pid,
            as_of_date=as_of_date,
            presentation_mode=presentation_mode,
        ),
        db,
        effective_ledger_id,
        period_id,
        as_of_date,
    )
    ledger_name, period_code = _ledger_and_period_meta(db, effective_ledger_id, period_id)
    signature = ReportSignature.from_params(
        preparer_name=preparer_name,
        reviewer_name=reviewer_name,
        approver_name=approver_name,
    )
    return _export_report_response(
        "balance_sheet",
        report,
        ledger_name=ledger_name,
        period_code=period_code or report.get("period_code"),
        fmt=format.lower(),
        signature=signature,
    )


@router.get("/income-statement/export")
def export_income_statement(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    format: str = "xlsx",
    preparer_name: str | None = None,
    reviewer_name: str | None = None,
    approver_name: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出利润表（xlsx / csv / pdf 签章版）。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    report = _run_report(
        financial_statements_service.income_statement,
        db,
        effective_ledger_id,
        period_id,
    )
    ledger_name, period_code = _ledger_and_period_meta(db, effective_ledger_id, period_id)
    signature = ReportSignature.from_params(
        preparer_name=preparer_name,
        reviewer_name=reviewer_name,
        approver_name=approver_name,
    )
    return _export_report_response(
        "income_statement",
        report,
        ledger_name=ledger_name,
        period_code=period_code,
        fmt=format.lower(),
        signature=signature,
    )


@router.get("/cash-flow-statement/export")
def export_cash_flow_statement(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    as_of_date: date | None = None,
    format: str = "xlsx",
    preparer_name: str | None = None,
    reviewer_name: str | None = None,
    approver_name: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出现金流量表（xlsx / csv / pdf 签章版）。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    report = _run_report(
        financial_statements_service.cash_flow_statement,
        db,
        effective_ledger_id,
        period_id,
        as_of_date,
    )
    ledger_name, period_code = _ledger_and_period_meta(db, effective_ledger_id, period_id)
    signature = ReportSignature.from_params(
        preparer_name=preparer_name,
        reviewer_name=reviewer_name,
        approver_name=approver_name,
    )
    return _export_report_response(
        "cash_flow",
        report,
        ledger_name=ledger_name,
        period_code=period_code or report.get("period_code"),
        fmt=format.lower(),
        signature=signature,
    )


@router.get("/package/export")
def export_reports_package(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    as_of_date: date | None = None,
    include_pdf: bool = True,
    preparer_name: str | None = None,
    reviewer_name: str | None = None,
    approver_name: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """打包导出四大报表（xlsx + 可选 pdf 签章版）。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    ledger_name, period_code = _ledger_and_period_meta(db, effective_ledger_id, period_id)
    signature = ReportSignature.from_params(
        preparer_name=preparer_name,
        reviewer_name=reviewer_name,
        approver_name=approver_name,
    )

    trial = _run_report(
        financial_statements_service.trial_balance_report,
        db, effective_ledger_id, period_id, as_of_date,
    )
    balance = _run_report(
        lambda db, lid, pid, as_of_date=None: financial_statements_service.balance_sheet(
            db, lid, pid, as_of_date=as_of_date,
        ),
        db, effective_ledger_id, period_id, as_of_date,
    )
    income = _run_report(
        financial_statements_service.income_statement,
        db, effective_ledger_id, period_id, as_of_date,
    )
    cash_flow = _run_report(
        financial_statements_service.cash_flow_statement,
        db, effective_ledger_id, period_id, as_of_date,
    )

    package_files: list[tuple[str, bytes]] = []
    for kind, report in [
        ("trial_balance", trial),
        ("balance_sheet", balance),
        ("income_statement", income),
        ("cash_flow", cash_flow),
    ]:
        xlsx_builder = EXPORT_BUILDERS[kind]["xlsx"]
        package_files.append((REPORT_XLSX_FILENAMES[kind], xlsx_builder(report, ledger_name=ledger_name)))
        if include_pdf:
            pdf_builder = PDF_BUILDERS[kind]
            if kind in {"income_statement", "cash_flow"}:
                pdf_body = pdf_builder(report, signature, period_code=period_code, ledger_name=ledger_name)
            else:
                pdf_body = pdf_builder(report, signature, ledger_name=ledger_name)
            package_files.append((REPORT_PDF_FILENAMES[kind], pdf_body))

    zip_body = build_reports_zip_package(package_files)
    filename = build_reports_package_filename(ledger_name=ledger_name, period_code=period_code)
    return StreamingResponse(
        iter([zip_body]),
        media_type=CONTENT_TYPES["zip"],
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )


@router.post("/package/deliver")
def deliver_reports_to_disk(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    as_of_date: date | None = None,
    include_pdf: bool = True,
    include_subsidiary: bool = True,
    preparer_name: str | None = None,
    reviewer_name: str | None = None,
    approver_name: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    生成标准格式财务报表并落盘到交付目录，供审计/军工审查单位邮递。
    默认目录：audit-platform-main/exports/audit-delivery/
    """
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    from app.services.accounting.report_delivery_service import deliver_reports_package

    try:
        return deliver_reports_package(
            db,
            ledger_id=effective_ledger_id,
            period_id=period_id,
            as_of_date=as_of_date,
            include_pdf=include_pdf,
            include_subsidiary=include_subsidiary,
            preparer_name=preparer_name,
            reviewer_name=reviewer_name,
            approver_name=approver_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/cash-flow-statement")
def cash_flow_statement(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """现金流量表（简化直接法）：返回经营、投资、筹资活动现金流量净额。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    return _run_report(
        financial_statements_service.cash_flow_statement,
        db,
        effective_ledger_id,
        period_id,
    )


def _resolve_ledger_id(db: Session, ledger_id: int | None, organization_id: int | None, period_id: int) -> int:
    """解析有效账簿ID：优先使用ledger_id，否则从organization_id或period_id推导。"""
    if ledger_id is not None:
        return ledger_id
    if organization_id is not None:
        period = db.get(AccountingPeriod, period_id)
        if period and period.organization_id == organization_id:
            if period.ledger_id is None:
                raise HTTPException(status_code=400, detail="会计期间未关联账簿")
            return period.ledger_id
        raise HTTPException(status_code=400, detail="organization_id与period_id不匹配")
    period = db.get(AccountingPeriod, period_id)
    if period:
        if period.ledger_id is None:
            raise HTTPException(status_code=400, detail="会计期间未关联账簿")
        return period.ledger_id
    raise HTTPException(status_code=404, detail="无法确定账簿ID")
