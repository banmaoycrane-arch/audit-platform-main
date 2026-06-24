from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, EntryTag
from app.db.session import get_db
from app.schemas.accounting_entry import AccountingEntryRead, TagUpdate
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


@router.get("", response_model=list[AccountingEntryRead])
def list_entries(
    import_job_id: int | None = None,
    ledger_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[AccountingEntry]:
    query = db.query(AccountingEntry).order_by(
        AccountingEntry.voucher_date.asc(),
        AccountingEntry.voucher_no.asc(),
        AccountingEntry.entry_line_no.asc(),
        AccountingEntry.id.asc(),
    )
    if import_job_id:
        query = query.filter(AccountingEntry.import_job_id == import_job_id)
    elif ledger_id is not None:
        query = query.filter(AccountingEntry.ledger_id == ledger_id)
    return query.limit(500).all()


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
