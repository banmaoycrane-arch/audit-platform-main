from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models import AccountingEntry, EntryTag
from app.db.session import get_db
from app.models.user import User
from app.schemas.accounting_entry import AccountingEntryRead, TagUpdate
from app.services import ledger_management_service
from app.services.entry_query_service import query_chronological_entries, query_vouchers
from app.services.vector_store_service import safe_vector_store

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
    voucher_no: str | None
    voucher_date: str | None
    voucher_word: str | None = None
    line_count: int
    debit_total: float
    credit_total: float
    summary_preview: str | None = None
    lines: list[VoucherLineRead]


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


def _tag_to_dict(tag: EntryTag) -> dict:
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
    limit: int = Query(100, ge=1, le=1000),
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
    return EntryListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/chronological", response_model=ChronologicalEntryListResponse)
def list_chronological_entries(
    ledger_id: int = Query(..., description="账簿 ID"),
    period_id: int | None = Query(None, description="会计期间 ID"),
    date_from: date | None = Query(None, description="凭证日期起"),
    date_to: date | None = Query(None, description="凭证日期止"),
    account_code: str | None = Query(None, description="科目代码（模糊）"),
    account_name: str | None = Query(None, description="科目名称（模糊）"),
    summary: str | None = Query(None, description="分录摘要（模糊）"),
    voucher_word: str | None = Query(None, description="记字号/凭证字，如 记、收、付、转"),
    voucher_no: str | None = Query(None, description="凭证号（模糊）"),
    amount_min: Decimal | None = Query(None, description="金额下限（借或贷）"),
    amount_max: Decimal | None = Query(None, description="金额上限（借或贷）"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChronologicalEntryListResponse:
    """序时簿：按时间顺序查看分录，支持科目、摘要、金额、日期、记字号等筛选。"""
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")

    items, total = query_chronological_entries(
        db,
        ledger_id=ledger_id,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        account_code=account_code,
        account_name=account_name,
        summary=summary,
        voucher_word=voucher_word,
        voucher_no=voucher_no,
        amount_min=amount_min,
        amount_max=amount_max,
        limit=limit,
        offset=offset,
    )
    return ChronologicalEntryListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
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


def _voucher_card_from_group(group) -> VoucherCardRead:
    return VoucherCardRead(
        voucher_no=group.voucher_no,
        voucher_date=group.voucher_date.isoformat() if group.voucher_date else None,
        voucher_word=_parse_voucher_word(group.voucher_no),
        line_count=len(group.lines),
        debit_total=group.debit_total,
        credit_total=group.credit_total,
        summary_preview=group.summary_preview or None,
        lines=group.lines,
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
    limit: int = Query(10, ge=1, le=100),
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
        limit=limit,
        offset=offset,
    )
    return VoucherQueryResponse(
        items=[_voucher_card_from_group(group) for group in groups],
        total=total,
        limit=limit,
        offset=offset,
    )


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
def update_tags(entry_id: int, payload: TagUpdate, db: Session = Depends(get_db)) -> dict:
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
def similar_search(entry_id: int, db: Session = Depends(get_db)) -> dict:
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
def list_tags(entry_id: int, db: Session = Depends(get_db)) -> list[dict]:
    entry = db.get(AccountingEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="分录不存在")
    tags = db.query(EntryTag).filter(EntryTag.entry_id == entry_id).all()
    return [_tag_to_dict(tag) for tag in tags]


@router.post("/{entry_id}/tags")
def create_tag(entry_id: int, payload: EntryTagCreate, db: Session = Depends(get_db)) -> dict:
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
def delete_tag(entry_id: int, tag_id: int, db: Session = Depends(get_db)) -> dict:
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
def batch_update_entry_review(payload: EntryBatchReviewUpdate, db: Session = Depends(get_db)) -> dict:
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
) -> dict:
    if payload.review_status not in VALID_ENTRY_REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail="无效的复核状态")
    updated = (
        db.query(AccountingEntry)
        .filter(AccountingEntry.import_job_id == job_id)
        .update({AccountingEntry.review_status: payload.review_status}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}
