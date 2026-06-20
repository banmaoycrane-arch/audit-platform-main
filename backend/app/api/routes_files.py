import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import Counterparty, ImportJob, SourceFile
from app.db.session import get_db

router = APIRouter(prefix="/api/files", tags=["files"])


class BindCounterpartyRequest(BaseModel):
    counterparty_id: int | None = None


def _extract_parse_summary(item: SourceFile) -> dict[str, Any]:
    if not item.extracted_text:
        return {"summary": None, "counterparty_hint": None, "raw_preview": None}

    try:
        parsed_text = json.loads(item.extracted_text)
    except json.JSONDecodeError:
        return {
            "summary": item.extracted_text[:200],
            "counterparty_hint": None,
            "raw_preview": item.extracted_text[:1000],
        }

    if not isinstance(parsed_text, dict):
        return {"summary": str(parsed_text)[:200], "counterparty_hint": None, "raw_preview": None}

    parse_feedback = parsed_text.get("parse_feedback")
    raw_preview = parsed_text.get("raw_text_preview")
    if isinstance(parse_feedback, dict):
        summary = parse_feedback.get("summary") or raw_preview
        counterparty_hint = parse_feedback.get("counterparty")
        return {
            "summary": str(summary)[:200] if summary else None,
            "counterparty_hint": str(counterparty_hint) if counterparty_hint else None,
            "raw_preview": str(raw_preview)[:1000] if raw_preview else None,
        }

    summary = parsed_text.get("summary") or raw_preview
    counterparty_hint = parsed_text.get("counterparty")
    return {
        "summary": str(summary)[:200] if summary else None,
        "counterparty_hint": str(counterparty_hint) if counterparty_hint else None,
        "raw_preview": str(raw_preview)[:1000] if raw_preview else None,
    }


def _find_counterparty_match(db: Session, item: SourceFile) -> tuple[Counterparty | None, str | None, str | None]:
    parsed = _extract_parse_summary(item)
    counterparties = db.query(Counterparty).filter(Counterparty.is_active == True).all()
    search_sources = [
        ("文件名", item.filename or ""),
        ("解析摘要", parsed.get("summary") or ""),
        ("对方单位字段", parsed.get("counterparty_hint") or ""),
    ]

    for source_name, source_text in search_sources:
        if not source_text:
            continue
        for counterparty in counterparties:
            if counterparty.name and counterparty.name in source_text:
                return counterparty, source_name, f"{source_name}包含往来单位名称“{counterparty.name}”，置信度较高"

    return None, None, "未从文件名、解析摘要或对方单位字段匹配到已有往来单位，请手工选择"


def _ensure_file_context(db: Session, item: SourceFile) -> None:
    if item.counterparty_id:
        return
    matched, source, note = _find_counterparty_match(db, item)
    if matched:
        item.counterparty_id = matched.id
        item.customer_match_source = source
        item.customer_confidence_note = note
        db.commit()
        db.refresh(item)
    elif not item.customer_confidence_note:
        item.customer_match_source = None
        item.customer_confidence_note = note
        db.commit()
        db.refresh(item)


def _to_dict(db: Session, item: SourceFile) -> dict[str, Any]:
    _ensure_file_context(db, item)
    parsed = _extract_parse_summary(item)
    counterparty = db.get(Counterparty, item.counterparty_id) if item.counterparty_id else None
    return {
        "id": item.id,
        "organization_id": item.organization_id,
        "import_job_id": item.import_job_id,
        "ledger_id": item.ledger_id,
        "filename": item.filename,
        "file_type": item.file_type,
        "text_extract_status": item.text_extract_status,
        "parse_status": item.text_extract_status,
        "parse_summary": parsed.get("summary"),
        "raw_text_preview": parsed.get("raw_preview"),
        "counterparty_id": item.counterparty_id,
        "counterparty_name": counterparty.name if counterparty else None,
        "customer_context": {
            "counterparty_id": item.counterparty_id,
            "counterparty_name": counterparty.name if counterparty else None,
            "match_source": item.customer_match_source,
            "confidence_note": item.customer_confidence_note,
        },
        "created_at": item.created_at,
    }


@router.get("")
def list_source_files(
    import_job_id: int | None = None,
    ledger_id: int | None = None,
    counterparty_id: int | None = None,
    customer_id: int | None = None,
    file_type: str | None = None,
    parse_status: str | None = None,
    text_extract_status: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(SourceFile).outerjoin(ImportJob, SourceFile.import_job_id == ImportJob.id)
    if import_job_id:
        query = query.filter(SourceFile.import_job_id == import_job_id)
    if ledger_id:
        query = query.filter(or_(SourceFile.ledger_id == ledger_id, ImportJob.ledger_id == ledger_id))
    selected_counterparty_id = counterparty_id or customer_id
    if selected_counterparty_id:
        query = query.filter(SourceFile.counterparty_id == selected_counterparty_id)
    if file_type:
        query = query.filter(SourceFile.file_type == file_type)
    selected_status = parse_status or text_extract_status
    if selected_status:
        query = query.filter(SourceFile.text_extract_status == selected_status)

    items = query.order_by(SourceFile.id.desc()).limit(200).all()
    return [_to_dict(db, item) for item in items]


@router.get("/{file_id}")
def get_source_file(file_id: int, db: Session = Depends(get_db)) -> dict:
    item = db.get(SourceFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="文件不存在")
    data = _to_dict(db, item)
    data["extracted_text"] = item.extracted_text
    return data


@router.post("/{file_id}/bind-counterparty")
def bind_file_counterparty(file_id: int, payload: BindCounterpartyRequest, db: Session = Depends(get_db)) -> dict:
    item = db.get(SourceFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="文件不存在")
    if payload.counterparty_id is not None:
        counterparty = db.get(Counterparty, payload.counterparty_id)
        if not counterparty or not counterparty.is_active:
            raise HTTPException(status_code=404, detail="往来单位不存在或已停用")
        item.counterparty_id = counterparty.id
        item.customer_match_source = "手工选择"
        item.customer_confidence_note = f"用户手工绑定往来单位“{counterparty.name}”"
    else:
        item.counterparty_id = None
        item.customer_match_source = None
        item.customer_confidence_note = "已取消手工绑定，请重新选择或等待系统自动匹配"
    db.commit()
    db.refresh(item)
    return _to_dict(db, item)
