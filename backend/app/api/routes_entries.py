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
        AccountingEntry.voucher_no.asc(),
        AccountingEntry.entry_line_no.asc(),
        AccountingEntry.id.asc(),
    )
    if import_job_id:
        query = query.filter(AccountingEntry.import_job_id == import_job_id)
    elif ledger_id is not None:
        query = query.filter(AccountingEntry.ledger_id == ledger_id)
    return query.limit(200).all()


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
