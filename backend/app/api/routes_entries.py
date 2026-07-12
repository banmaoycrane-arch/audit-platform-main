from typing import Any
from datetime import date
from decimal import Decimal, InvalidOperation
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models import AccountingEntry, EntryTag, SourceFile, Voucher
from app.db.session import get_db
from app.models.user import User
from app.schemas.accounting_entry import AccountingEntryRead, TagUpdate
from app.services.shared import ledger_management_service
from app.services.accounting.entry_delete_service import VoucherDeleteKey, delete_vouchers_transactional
from app.services.accounting.entry_query_service import load_voucher_lines, query_chronological_entries, query_vouchers
from app.services.accounting.voucher_card_resolver import resolve_voucher_card_fields, resolve_voucher_card_fields_from_slim_rows
from app.services.accounting.voucher_review_service import (
    review_voucher,
    review_vouchers_batch,
    unreview_voucher,
)
from app.services.doc_parsing.draft_archive_service import get_evidence_lifecycle, load_archive_metadata

router = APIRouter(prefix="/api/entries", tags=["entries"])


VALID_ENTRY_REVIEW_STATUSES = {"draft", "verified", "ready"}


class EntryTagCreate(BaseModel):
    tag_name: str | None = None
    tag_type: str | None = None
    tag_value: str | None = None
    tag_value_normalized: str | None = None
    tag_source: str = "manual"
    confidence: float = 1.0
    reviewed_by_user: bool = True


class EntryReviewUpdate(BaseModel):
    review_status: str


class EntryBatchReviewUpdate(BaseModel):
    entry_ids: list[int]
    review_status: str


class EntryJobReviewUpdate(BaseModel):
    review_status: str


class VoucherDeleteItem(BaseModel):
    voucher_no: str | None = None
    voucher_date: date | None = None


class VoucherBatchDeleteRequest(BaseModel):
    ledger_id: int
    vouchers: list[VoucherDeleteItem]


class VoucherBatchDeleteResponse(BaseModel):
    deleted_vouchers: int
    deleted_entries: int


class EntryReviewStatsResponse(BaseModel):
    total: int
    verified: int
    ready: int
    unreviewed: int
    status_counts: dict[str, int]


class EntryListResponse(BaseModel):
    items: list[AccountingEntryRead]
    total: int
    limit: int
    offset: int


class ChronologicalEntryListResponse(BaseModel):
    items: list[AccountingEntryRead]
    total: int
    limit: int
    offset: int


class VoucherLineRead(AccountingEntryRead):
    pass


class VoucherCardRead(BaseModel):
    voucher_id: int | None = None
    voucher_no: str | None
    voucher_date: str | None
    voucher_word: str | None = None
    status: str | None = None
    line_count: int
    debit_total: float
    credit_total: float
    summary_preview: str | None = None
    lines: list[VoucherLineRead] = []


class VoucherLinesResponse(BaseModel):
    items: list[VoucherLineRead]


class VoucherQueryResponse(BaseModel):
    items: list[VoucherCardRead]
    total: int
    limit: int
    offset: int


class EntryFieldUpdate(BaseModel):
    voucher_no: str | None = None
    voucher_date: date | None = None
    summary: str | None = None
    account_code: str | None = None
    account_name: str | None = None
    debit_amount: Decimal | None = None
    credit_amount: Decimal | None = None
    counterparty: str | None = None


def _normalize_money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.00"))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail="金额格式不正确") from exc
    if amount < 0:
        raise HTTPException(status_code=400, detail="借方或贷方金额不能为负数")
    return amount


def _validate_entry_amounts(debit_amount: Decimal | None, credit_amount: Decimal | None) -> None:
    debit = debit_amount or Decimal("0.00")
    credit = credit_amount or Decimal("0.00")
    if debit > 0 and credit > 0:
        raise HTTPException(status_code=400, detail="同一分录不能同时填写借方和贷方金额")
    if debit == 0 and credit == 0:
        raise HTTPException(status_code=400, detail="分录至少需要填写借方或贷方金额")


def _tag_to_dict(tag: EntryTag) -> dict[str, Any]:
    return {
        "id": tag.id,
        "entry_id": tag.entry_id,
        "tag_name": tag.tag_name,
        "tag_type": tag.tag_type,
        "tag_value": tag.tag_value,
        "tag_value_normalized": tag.tag_value_normalized,
        "tag_source": tag.tag_source,
        "confidence": tag.confidence,
        "reviewed_by_user": tag.reviewed_by_user,
        "vector_pending": tag.vector_pending,
        "created_at": tag.created_at.isoformat() if tag.created_at else None,
    }


@router.get("/review-stats", response_model=EntryReviewStatsResponse)
def get_entry_review_stats(
    import_job_id: int | None = None,
    ledger_id: int | None = None,
    db: Session = Depends(get_db),
) -> EntryReviewStatsResponse:
    query = db.query(AccountingEntry.review_status, func.count(AccountingEntry.id))
    if import_job_id:
        query = query.filter(AccountingEntry.import_job_id == import_job_id)
    elif ledger_id is not None:
        query = query.filter(AccountingEntry.ledger_id == ledger_id)
    rows = query.group_by(AccountingEntry.review_status).all()
    status_counts = {str(status or "draft"): int(count) for status, count in rows}
    total = sum(status_counts.values())
    verified = status_counts.get("verified", 0)
    ready = status_counts.get("ready", 0)
    return EntryReviewStatsResponse(
        total=total,
        verified=verified,
        ready=ready,
        unreviewed=total - verified - ready,
        status_counts=status_counts,
    )


@router.get("", response_model=EntryListResponse)
def list_entries(
    import_job_id: int | None = None,
    ledger_id: int | None = None,
    review_status: str | None = Query(None, description="复核状态筛选：draft/verified/ready"),
    date_from: date | None = Query(None, description="凭证日期起"),
    date_to: date | None = Query(None, description="凭证日期止"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> EntryListResponse:
    query = db.query(AccountingEntry)
    if import_job_id:
        query = query.filter(AccountingEntry.import_job_id == import_job_id)
    elif ledger_id is not None:
        query = query.filter(AccountingEntry.ledger_id == ledger_id)
    if review_status:
        if review_status not in VALID_ENTRY_REVIEW_STATUSES:
            raise HTTPException(status_code=400, detail="无效的复核状态")
        query = query.filter(AccountingEntry.review_status == review_status)
    if date_from:
        query = query.filter(AccountingEntry.voucher_date >= date_from)
    if date_to:
        query = query.filter(AccountingEntry.voucher_date <= date_to)
    total = query.count()
    items = (
        query.order_by(
            AccountingEntry.voucher_no.asc(),
            AccountingEntry.entry_line_no.asc(),
            AccountingEntry.id.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return EntryListResponse(items=[AccountingEntryRead.model_validate(item) for item in items], total=total, limit=limit, offset=offset)


@router.get("/chronological", response_model=ChronologicalEntryListResponse)
def list_chronological_entries(
    ledger_id: int = Query(..., description="账簿 ID"),
    period_id: int | None = Query(None, description="会计期间 ID"),
    period_ids: str | None = Query(None, description="多会计期间 JSON 数组，如 [1,2,3]"),
    date_from: date | None = Query(None, description="凭证日期起"),
    date_to: date | None = Query(None, description="凭证日期止"),
    account_code: str | None = Query(None, description="科目代码"),
    account_codes: str | None = Query(None, description="多科目 JSON 数组，如 [\"1001\",\"1002\"]"),
    account_code_match: str = Query(
        "contains",
        description="科目匹配方式：exact 精确 / prefix 本级及下级 / contains 模糊",
    ),
    account_name: str | None = Query(None, description="科目名称（模糊）"),
    summary: str | None = Query(None, description="分录摘要（模糊）"),
    voucher_word: str | None = Query(None, description="记字号/凭证字，如 记、收、付、转"),
    voucher_no: str | None = Query(None, description="凭证号（模糊）"),
    amount_min: Decimal | None = Query(None, description="金额下限（借或贷）"),
    amount_max: Decimal | None = Query(None, description="金额上限（借或贷）"),
    tag_category_code: str | None = Query(None, description="维度分类 code"),
    tag_value: str | None = Query(None, description="维度 tag 值"),
    tag_filters: str | None = Query(None, description="多维组合筛选 JSON：[{category_code,tag_value}]"),
    counterparty: str | None = Query(None, description="往来单位（模糊）"),
    tag_match_scope: str = Query(
        "entry",
        description="tag 匹配范围：entry 仅本分录行 / voucher 同凭证任一行（明细账对方科目维度）",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChronologicalEntryListResponse:
    """序时簿：按时间顺序查看分录，支持科目、摘要、金额、日期、记字号等筛选。"""
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")

    from app.services.accounting.entry_query_service import parse_account_codes, parse_period_ids
    from app.services.accounting.subsidiary_ledger_service import _parse_tag_filters

    resolved_codes = parse_account_codes(account_codes, fallback=account_code)
    resolved_period_ids = parse_period_ids(period_ids, fallback=period_id)
    items, total = query_chronological_entries(
        db,
        ledger_id=ledger_id,
        period_id=period_id if not period_ids else None,
        period_ids=resolved_period_ids or None,
        date_from=date_from,
        date_to=date_to,
        account_code=account_code if not resolved_codes else None,
        account_codes=resolved_codes or None,
        account_code_match=account_code_match,
        account_name=account_name,
        summary=summary,
        voucher_word=voucher_word,
        voucher_no=voucher_no,
        amount_min=amount_min,
        amount_max=amount_max,
        tag_category_code=tag_category_code,
        tag_value=tag_value,
        tag_filters=_parse_tag_filters(tag_filters),
        counterparty=counterparty,
        tag_match_scope=tag_match_scope,
        limit=limit,
        offset=offset,
    )
    return ChronologicalEntryListResponse(
        items=[AccountingEntryRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/ledger-account-codes")
def list_ledger_account_codes(
    ledger_id: int = Query(..., description="账簿 ID"),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """账簿内实际出现过的科目编码（用于明细账科目选择）。"""
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")
    rows = (
        db.query(
            AccountingEntry.account_code,
            AccountingEntry.account_name,
            func.count(AccountingEntry.id).label("entry_count"),
        )
        .filter(
            AccountingEntry.ledger_id == ledger_id,
            AccountingEntry.account_code.isnot(None),
            AccountingEntry.account_code != "",
        )
        .group_by(AccountingEntry.account_code, AccountingEntry.account_name)
        .order_by(AccountingEntry.account_code.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "account_code": row.account_code,
            "account_name": row.account_name,
            "entry_count": int(row.entry_count or 0),
        }
        for row in rows
    ]


@router.get("/subsidiary-ledger/opening-balance")
def subsidiary_ledger_opening_balance(
    ledger_id: int = Query(...),
    account_code: str | None = Query(None),
    account_codes: str | None = Query(None),
    account_code_match: str = Query(
        "prefix",
        description="明细账固定按科目汇总：含本级及全部下级明细科目分录",
    ),
    organization_id: int | None = Query(None),
    period_id: int | None = Query(None),
    period_ids: str | None = Query(None),
    date_from: date | None = Query(None),
    summary: str | None = Query(None),
    counterparty: str | None = Query(None),
    tag_category_code: str | None = Query(None),
    tag_value: str | None = Query(None),
    tag_filters: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")
    from app.services.accounting.entry_query_service import parse_account_codes, parse_period_ids
    from app.services.accounting.subsidiary_ledger_service import compute_subsidiary_opening_balance

    resolved_codes = parse_account_codes(account_codes, fallback=account_code)
    if not resolved_codes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一个科目")
    resolved_period_ids = parse_period_ids(period_ids, fallback=period_id)

    return compute_subsidiary_opening_balance(
        db,
        ledger_id=ledger_id,
        account_code=resolved_codes[0],
        account_codes=resolved_codes,
        account_code_match=account_code_match,
        organization_id=organization_id,
        period_id=period_id if not period_ids else None,
        period_ids=resolved_period_ids or None,
        date_from=date_from,
        summary=summary,
        counterparty=counterparty,
        tag_category_code=tag_category_code,
        tag_value=tag_value,
        tag_filters_raw=tag_filters,
    )


@router.get("/subsidiary-ledger/export")
def export_subsidiary_ledger(
    ledger_id: int = Query(...),
    account_code: str | None = Query(None),
    account_codes: str | None = Query(None),
    account_code_match: str = Query(
        "prefix",
        description="明细账固定按科目汇总：含本级及全部下级明细科目分录",
    ),
    period_id: int | None = Query(None),
    period_ids: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    summary: str | None = Query(None),
    counterparty: str | None = Query(None),
    tag_category_code: str | None = Query(None),
    tag_value: str | None = Query(None),
    tag_filters: str | None = Query(None),
    organization_id: int | None = Query(None),
    category_codes: str | None = Query(None, description="导出维度列，逗号分隔"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")
    from app.services.accounting.entry_query_service import parse_account_codes, parse_period_ids
    from app.services.accounting.subsidiary_ledger_service import (
        compute_subsidiary_opening_balance,
        export_subsidiary_ledger_xlsx,
    )

    resolved_codes = parse_account_codes(account_codes, fallback=account_code)
    if not resolved_codes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一个科目")
    resolved_period_ids = parse_period_ids(period_ids, fallback=period_id)

    opening = compute_subsidiary_opening_balance(
        db,
        ledger_id=ledger_id,
        account_code=resolved_codes[0],
        account_codes=resolved_codes,
        account_code_match=account_code_match,
        organization_id=organization_id,
        period_id=period_id if not period_ids else None,
        period_ids=resolved_period_ids or None,
        date_from=date_from,
        summary=summary,
        counterparty=counterparty,
        tag_category_code=tag_category_code,
        tag_value=tag_value,
        tag_filters_raw=tag_filters,
    )
    dim_codes = [code.strip() for code in (category_codes or "").split(",") if code.strip()]
    from app.db.models import AccountingPeriod
    from app.models.ledger import Ledger
    from app.services.accounting.export_filename_service import build_report_export_filename, content_disposition_attachment

    ledger = db.get(Ledger, ledger_id)
    period = db.get(AccountingPeriod, period_id) if period_id else None
    body = export_subsidiary_ledger_xlsx(
        db,
        ledger_id=ledger_id,
        account_code=resolved_codes[0],
        account_codes=resolved_codes,
        account_code_match=account_code_match,
        period_id=period_id if not period_ids else None,
        period_ids=resolved_period_ids or None,
        date_from=date_from,
        date_to=date_to,
        summary=summary,
        counterparty=counterparty,
        tag_category_code=tag_category_code,
        tag_value=tag_value,
        tag_filters_raw=tag_filters,
        opening_balance=opening["opening_balance"],
        direction=opening["direction"],
        category_codes=dim_codes,
        ledger_name=ledger.name if ledger else None,
        period_code=period.period_code if period else None,
    )
    filename = build_report_export_filename(
        "subsidiary_ledger",
        ledger_name=ledger.name if ledger else None,
        period_code=period.period_code if period else None,
        fmt="xlsx",
    )
    if filename.startswith("ledger_"):
        filename = f"05_明细账_{resolved_codes[0]}.xlsx"
    return StreamingResponse(
        iter([body]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )


def _parse_voucher_word(voucher_no: str | None) -> str | None:
    if not voucher_no:
        return None
    dash = voucher_no.find("-")
    if dash > 0:
        return voucher_no[:dash]
    prefix = ""
    for char in voucher_no:
        if char.isdigit():
            break
        prefix += char
    return prefix or voucher_no


def _voucher_card_from_group(group: Any, *, include_lines: bool = False) -> VoucherCardRead:
    return VoucherCardRead(
        voucher_id=group.voucher_id,
        voucher_no=group.voucher_no,
        voucher_date=group.voucher_date.isoformat() if group.voucher_date else None,
        voucher_word=_parse_voucher_word(group.voucher_no),
        status=group.status,
        line_count=group.line_count,
        debit_total=group.debit_total,
        credit_total=group.credit_total,
        summary_preview=group.summary_preview or None,
        lines=group.lines if include_lines else [],
    )


@router.get("/vouchers", response_model=VoucherQueryResponse)
def list_voucher_cards(
    ledger_id: int = Query(..., description="账簿 ID"),
    period_id: int | None = Query(None, description="会计期间 ID"),
    date_from: date | None = Query(None, description="凭证日期起（按天）"),
    date_to: date | None = Query(None, description="凭证日期止（按天）"),
    month: str | None = Query(None, description="凭证月份 YYYY-MM"),
    filter_mode: str = Query("line", description="line=按行筛选, voucher=按凭证整体筛选"),
    account_code: str | None = Query(None, description="科目代码（模糊）"),
    account_name: str | None = Query(None, description="科目名称（模糊）"),
    summary: str | None = Query(None, description="分录摘要（模糊）"),
    voucher_word: str | None = Query(None, description="记字号/凭证字"),
    voucher_no: str | None = Query(None, description="凭证号（模糊）"),
    debit_min: Decimal | None = Query(None, description="借方金额下限"),
    debit_max: Decimal | None = Query(None, description="借方金额上限"),
    credit_min: Decimal | None = Query(None, description="贷方金额下限"),
    credit_max: Decimal | None = Query(None, description="贷方金额上限"),
    total_min: Decimal | None = Query(None, description="凭证合计金额下限"),
    total_max: Decimal | None = Query(None, description="凭证合计金额上限"),
    import_job_id: int | None = Query(None, description="导入任务 ID（向导审核场景按批次筛选）"),
    review_status: str | None = Query(None, description="分录复核状态（如 pending / reviewed）"),
    include_lines: bool = Query(False, description="是否返回每张凭证的全部分录行（默认否，展开时再请求 /vouchers/lines）"),
    limit: int = Query(10, ge=1, le=500, description="单页最多返回的凭证张数"),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoucherQueryResponse:
    """凭证查询：按凭证聚合展示，支持按行或整体筛选。"""
    if filter_mode not in {"line", "voucher"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="filter_mode 必须为 line 或 voucher")
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")

    groups, total = query_vouchers(
        db,
        ledger_id=ledger_id,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        month=month,
        filter_mode=filter_mode,
        account_code=account_code,
        account_name=account_name,
        summary=summary,
        voucher_word=voucher_word,
        voucher_no=voucher_no,
        debit_min=debit_min,
        debit_max=debit_max,
        credit_min=credit_min,
        credit_max=credit_max,
        total_min=total_min,
        total_max=total_max,
        import_job_id=import_job_id,
        review_status=review_status,
        limit=limit,
        offset=offset,
        include_lines=include_lines,
    )
    return VoucherQueryResponse(
        items=[_voucher_card_from_group(group, include_lines=include_lines) for group in groups],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/vouchers/lines", response_model=VoucherLinesResponse)
def get_voucher_lines(
    ledger_id: int = Query(..., description="账簿 ID"),
    voucher_no: str | None = Query(None, description="凭证号"),
    voucher_date: date | None = Query(None, description="凭证日期"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoucherLinesResponse:
    """按单张凭证加载分录明细（凭证查询页展开时按需调用）。"""
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")
    lines = load_voucher_lines(
        db,
        ledger_id=ledger_id,
        voucher_no=voucher_no,
        voucher_date=voucher_date,
    )
    if not lines:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")
    return VoucherLinesResponse(items=[VoucherLineRead.model_validate(line) for line in lines])


@router.get("/{entry_id}/source-evidence")
def get_entry_source_evidence(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """从分录反查证据云空间原件。"""
    entry = db.get(AccountingEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分录不存在")
    if entry.ledger_id and not ledger_management_service.user_has_ledger_access(
        db, current_user.id, entry.ledger_id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")
    if not entry.source_file_id:
        return {
            "entry_id": entry_id,
            "source_file_id": None,
            "linked": False,
            "evidence_path": None,
            "source_file": None,
        }
    source_file = db.get(SourceFile, entry.source_file_id)
    if not source_file:
        return {
            "entry_id": entry_id,
            "source_file_id": entry.source_file_id,
            "linked": False,
            "evidence_path": f"/ledger/files?fileId={entry.source_file_id}",
            "source_file": None,
        }
    archive = load_archive_metadata(source_file) or {}
    lifecycle = get_evidence_lifecycle(source_file)
    evidence_meta: dict[str, Any] = {}
    try:
        notes = json.loads(source_file.notes or "{}")
        raw = notes.get("evidence")
        if isinstance(raw, dict):
            evidence_meta = raw
    except json.JSONDecodeError:
        evidence_meta = {}
    return {
        "entry_id": entry_id,
        "source_file_id": source_file.id,
        "linked": True,
        "evidence_path": f"/ledger/files?fileId={source_file.id}",
        "source_file": {
            "id": source_file.id,
            "filename": source_file.filename,
            "file_type": source_file.file_type,
            "ledger_id": source_file.ledger_id,
            "parse_status": source_file.text_extract_status,
            "evidence_lifecycle": lifecycle,
            "ingest_channel": evidence_meta.get("ingest_channel"),
            "archive_category": archive.get("archive_category"),
            "period_code": archive.get("period_code"),
            "project_id": archive.get("project_id"),
        },
    }


@router.post("/vouchers/batch-delete", response_model=VoucherBatchDeleteResponse)
def batch_delete_vouchers(
    payload: VoucherBatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoucherBatchDeleteResponse:
    """按整张凭证批量删除分录，单事务提交，避免只删部分行导致借贷不平衡。"""
    if not payload.vouchers:
        return VoucherBatchDeleteResponse(deleted_vouchers=0, deleted_entries=0)
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, payload.ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")
    keys = [
        VoucherDeleteKey(voucher_no=item.voucher_no, voucher_date=item.voucher_date)
        for item in payload.vouchers
    ]
    try:
        result = delete_vouchers_transactional(db, ledger_id=payload.ledger_id, voucher_keys=keys)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除凭证失败: {exc}") from exc
    return VoucherBatchDeleteResponse(**result)


class VoucherReviewBatchRequest(BaseModel):
    voucher_ids: list[int]


@router.post("/vouchers/{voucher_id}/review")
def review_voucher_endpoint(voucher_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        voucher = review_voucher(db, voucher_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"voucher_id": voucher.id, "status": voucher.status, "reviewed": True}


@router.post("/vouchers/review-batch")
def review_vouchers_batch_endpoint(
    payload: VoucherReviewBatchRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        count = review_vouchers_batch(db, payload.voucher_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"reviewed_count": count}


@router.post("/vouchers/{voucher_id}/unreview")
def unreview_voucher_endpoint(voucher_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        voucher = unreview_voucher(db, voucher_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"voucher_id": voucher.id, "status": voucher.status, "reviewed": False}


@router.patch("/{entry_id}", response_model=AccountingEntryRead)
def update_entry_fields(
    entry_id: int,
    payload: EntryFieldUpdate,
    db: Session = Depends(get_db),
) -> AccountingEntry:
    entry = db.get(AccountingEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="分录不存在")
    if entry.review_status in {"verified", "ready"}:
        raise HTTPException(status_code=400, detail="已复核分录不能直接修改，请先取消复核")

    update_data = payload.model_dump(exclude_unset=True)
    if "summary" in update_data and not str(update_data["summary"] or "").strip():
        raise HTTPException(status_code=400, detail="摘要不能为空")
    if "account_code" in update_data and not str(update_data["account_code"] or "").strip():
        raise HTTPException(status_code=400, detail="科目代码不能为空")
    if "account_name" in update_data and not str(update_data["account_name"] or "").strip():
        raise HTTPException(status_code=400, detail="科目名称不能为空")

    debit_amount = _normalize_money(update_data.get("debit_amount", entry.debit_amount))
    credit_amount = _normalize_money(update_data.get("credit_amount", entry.credit_amount))
    _validate_entry_amounts(debit_amount, credit_amount)

    for field, value in update_data.items():
        if field in {"debit_amount", "credit_amount"}:
            setattr(entry, field, _normalize_money(value))
        elif isinstance(value, str):
            setattr(entry, field, value.strip() or None)
        else:
            setattr(entry, field, value)
    entry.normalized_text = " ".join(
        str(part or "")
        for part in [entry.voucher_no, entry.voucher_date, entry.summary, entry.account_code, entry.account_name, entry.counterparty]
    ).strip()
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/{entry_id}", response_model=AccountingEntryRead)
def get_entry(entry_id: int, db: Session = Depends(get_db)) -> AccountingEntry:
    entry = db.get(AccountingEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="分录不存在")
    return entry


@router.patch("/{entry_id}/tags")
def update_tags(entry_id: int, payload: TagUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    entry = db.get(AccountingEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="分录不存在")
    db.query(EntryTag).filter(EntryTag.entry_id == entry_id).delete()
    for tag in payload.tags:
        db.add(EntryTag(
            entry_id=entry_id,
            tag_name=tag,
            tag_type="manual",
            tag_value=tag,
            tag_value_normalized=tag.strip().lower(),
            tag_source="manual",
            confidence=1.0,
            reviewed_by_user=True,
            vector_pending=True,
        ))
    db.commit()
    return {"entry_id": entry_id, "tags": payload.tags}


@router.post("/{entry_id}/similar-search")
def similar_search(entry_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    entry = db.get(AccountingEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="分录不存在")
    store = safe_vector_store()
    if not store:
        return {"results": [], "message": "向量库当前不可用"}
    try:
        return {"results": store.search(entry.normalized_text)}
    except Exception as exc:
        return {"results": [], "message": str(exc)}


@router.get("/{entry_id}/tags")
def list_tags(entry_id: int, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    entry = db.get(AccountingEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="分录不存在")
    tags = db.query(EntryTag).filter(EntryTag.entry_id == entry_id).all()
    return [_tag_to_dict(tag) for tag in tags]


@router.post("/{entry_id}/tags")
def create_tag(entry_id: int, payload: EntryTagCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    entry = db.get(AccountingEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="分录不存在")
    tag_name = payload.tag_name or payload.tag_value or payload.tag_type or "manual_tag"
    normalize_source = payload.tag_value or tag_name
    tag = EntryTag(
        entry_id=entry_id,
        tag_name=tag_name,
        tag_type=payload.tag_type,
        tag_value=payload.tag_value,
        tag_value_normalized=payload.tag_value_normalized or normalize_source.strip().lower(),
        tag_source=payload.tag_source,
        confidence=payload.confidence,
        reviewed_by_user=payload.reviewed_by_user,
        vector_pending=True,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return _tag_to_dict(tag)


@router.delete("/{entry_id}/tags/{tag_id}")
def delete_tag(entry_id: int, tag_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    entry = db.get(AccountingEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="分录不存在")
    tag = db.get(EntryTag, tag_id)
    if not tag or tag.entry_id != entry_id:
        raise HTTPException(status_code=404, detail="标签不存在")
    db.delete(tag)
    db.commit()
    return {"deleted": 1}


@router.patch("/{entry_id}/review", response_model=AccountingEntryRead)
def update_entry_review(
    entry_id: int,
    payload: EntryReviewUpdate,
    db: Session = Depends(get_db),
) -> AccountingEntry:
    if payload.review_status not in VALID_ENTRY_REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail="无效的复核状态")
    entry = db.get(AccountingEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="分录不存在")
    entry.review_status = payload.review_status
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/batch-review")
def batch_update_entry_review(payload: EntryBatchReviewUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    if payload.review_status not in VALID_ENTRY_REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail="无效的复核状态")
    if not payload.entry_ids:
        return {"updated": 0}
    updated = (
        db.query(AccountingEntry)
        .filter(AccountingEntry.id.in_(payload.entry_ids))
        .update({AccountingEntry.review_status: payload.review_status}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}


@router.post("/jobs/{job_id}/review-all")
def review_all_entries_for_job(
    job_id: int,
    payload: EntryJobReviewUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.review_status not in VALID_ENTRY_REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail="无效的复核状态")
    updated = (
        db.query(AccountingEntry)
        .filter(AccountingEntry.import_job_id == job_id)
        .update({AccountingEntry.review_status: payload.review_status}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}
