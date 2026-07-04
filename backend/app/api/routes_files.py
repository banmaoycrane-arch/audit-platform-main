import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import Counterparty, ImportJob, SourceFile
from app.db.session import get_db
from app.services.doc_parsing.draft_archive_service import load_archive_metadata

router = APIRouter(prefix="/api/files", tags=["files"])


class BindCounterpartyRequest(BaseModel):
    counterparty_id: int | None = None


class BindLedgerRequest(BaseModel):
    ledger_id: int | None = None


class UpdateFileRequest(BaseModel):
    filename: str | None = None
    file_type: str | None = None
    notes: str | None = None


def _collect_object_names(value: Any) -> list[str]:
    names: list[str] = []
    keys = {
        "counterparty", "counterparty_name", "customer", "customer_name", "client", "client_name",
        "supplier", "supplier_name", "vendor", "vendor_name", "buyer", "buyer_name",
        "seller", "seller_name", "purchaser", "party_a", "party_a_name", "party_b", "party_b_name",
        "甲方", "乙方", "购货方", "销货方", "购买方", "销售方",
    }

    def add_name(raw: Any) -> None:
        if raw is None:
            return
        if isinstance(raw, (list, tuple, set)):
            for item in raw:
                add_name(item)
            return
        text = str(raw).strip()
        if text and text not in names:
            names.append(text)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                if str(key) in keys:
                    add_name(item)
                if isinstance(item, (dict, list)):
                    walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return names


def _extract_parse_summary(item: SourceFile) -> dict[str, Any]:
    if not item.extracted_text:
        return {"summary": None, "counterparty_hint": None, "object_names": [], "raw_preview": None}

    try:
        parsed_text = json.loads(item.extracted_text)
    except json.JSONDecodeError:
        return {
            "summary": item.extracted_text[:200],
            "counterparty_hint": None,
            "object_names": [],
            "raw_preview": item.extracted_text[:1000],
        }

    if not isinstance(parsed_text, dict):
        return {"summary": str(parsed_text)[:200], "counterparty_hint": None, "object_names": [], "raw_preview": None}

    parse_feedback = parsed_text.get("parse_feedback")
    raw_preview = parsed_text.get("raw_text_preview")
    object_names = _collect_object_names(parsed_text)
    if isinstance(parse_feedback, dict):
        summary = parse_feedback.get("summary") or raw_preview
        counterparty_hint = parse_feedback.get("counterparty")
        return {
            "summary": str(summary)[:200] if summary else None,
            "counterparty_hint": str(counterparty_hint) if counterparty_hint else (object_names[0] if object_names else None),
            "object_names": object_names,
            "raw_preview": str(raw_preview)[:1000] if raw_preview else None,
        }

    summary = parsed_text.get("summary") or raw_preview
    counterparty_hint = parsed_text.get("counterparty")
    return {
        "summary": str(summary)[:200] if summary else None,
        "counterparty_hint": str(counterparty_hint) if counterparty_hint else (object_names[0] if object_names else None),
        "object_names": object_names,
        "raw_preview": str(raw_preview)[:1000] if raw_preview else None,
    }


def _find_counterparty_match(db: Session, item: SourceFile) -> tuple[Counterparty | None, str | None, str | None]:
    parsed = _extract_parse_summary(item)
    counterparties = db.query(Counterparty).filter(Counterparty.is_active == True).all()
    search_sources = [
        ("文件名", item.filename or ""),
        ("解析摘要", parsed.get("summary") or ""),
        ("对象名称", " ".join(parsed.get("object_names") or [])),
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
    archive = load_archive_metadata(item)
    object_names = list(parsed.get("object_names") or [])
    archive_counterparty = archive.get("counterparty") if archive else None
    if archive_counterparty and archive_counterparty not in object_names:
        object_names.append(str(archive_counterparty))
    if counterparty and counterparty.name not in object_names:
        object_names.insert(0, counterparty.name)
    object_name = object_names[0] if object_names else (parsed.get("counterparty_hint") or None)
    return {
        "id": item.id,
        "organization_id": item.organization_id,
        "import_job_id": item.import_job_id,
        "ledger_id": item.ledger_id,
        "filename": item.filename,
        "file_type": item.file_type,
        "notes": item.notes,
        "text_extract_status": item.text_extract_status,
        "parse_status": item.text_extract_status,
        "parse_summary": parsed.get("summary"),
        "raw_text_preview": parsed.get("raw_preview"),
        "counterparty_id": item.counterparty_id,
        "counterparty_name": counterparty.name if counterparty else None,
        "object_name": object_name,
        "object_names": object_names,
        "customer_context": {
            "counterparty_id": item.counterparty_id,
            "counterparty_name": counterparty.name if counterparty else None,
            "match_source": item.customer_match_source,
            "confidence_note": item.customer_confidence_note,
        },
        "archive_path": archive.get("archive_path") if archive else None,
        "archive_category": archive.get("archive_category") if archive else None,
        "archive_folder": archive.get("archive_folder") if archive else None,
        "project_id": archive.get("project_id") if archive else None,
        "project_name": archive.get("project_name") if archive else None,
        "period_code": archive.get("period_code") if archive else None,
        "archive_context": archive,
        "created_at": item.created_at,
    }


def _parse_id_list(value: str | None) -> list[int]:
    if not value:
        return []
    ids: list[int] = []
    for part in value.split(","):
        text = part.strip()
        if text.isdigit():
            ids.append(int(text))
    return ids


def _effective_ledger_id(item: SourceFile) -> int | None:
    if item.ledger_id is not None:
        return item.ledger_id
    if item.import_job_id and item.import_job:
        return item.import_job.ledger_id
    return None


@router.get("")
def list_source_files(
    import_job_id: int | None = None,
    ledger_id: int | None = None,
    ledger_ids: str | None = None,
    project_id: int | None = None,
    counterparty_id: int | None = None,
    customer_id: int | None = None,
    object_name: str | None = None,
    file_type: str | None = None,
    parse_status: str | None = None,
    text_extract_status: str | None = None,
    archive_category: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    selected_ledger_ids = _parse_id_list(ledger_ids)
    if ledger_id is not None:
        selected_ledger_ids.append(ledger_id)
    selected_ledger_ids = sorted(set(selected_ledger_ids))

    if project_id:
        from app.services.doc_parsing.draft_archive_service import list_project_archived_files

        items = list_project_archived_files(db, project_id)
        if selected_ledger_ids:
            items = [item for item in items if _effective_ledger_id(item) in selected_ledger_ids]
        if archive_category:
            items = [
                item
                for item in items
                if (load_archive_metadata(item) or {}).get("archive_category") == archive_category
            ]
        selected_counterparty_id = counterparty_id or customer_id
        if selected_counterparty_id:
            items = [item for item in items if item.counterparty_id == selected_counterparty_id]
        if file_type:
            items = [item for item in items if item.file_type == file_type]
        selected_status = parse_status or text_extract_status
        if selected_status:
            items = [item for item in items if item.text_extract_status == selected_status]
        if object_name:
            items = [item for item in items if object_name in (_to_dict(db, item).get("object_names") or [])]
        return [_to_dict(db, item) for item in items]

    query = db.query(SourceFile).outerjoin(ImportJob, SourceFile.import_job_id == ImportJob.id)
    if import_job_id:
        query = query.filter(SourceFile.import_job_id == import_job_id)
    if selected_ledger_ids:
        query = query.filter(or_(SourceFile.ledger_id.in_(selected_ledger_ids), ImportJob.ledger_id.in_(selected_ledger_ids)))
    selected_counterparty_id = counterparty_id or customer_id
    if selected_counterparty_id:
        query = query.filter(SourceFile.counterparty_id == selected_counterparty_id)
    if file_type:
        query = query.filter(SourceFile.file_type == file_type)
    selected_status = parse_status or text_extract_status
    if selected_status:
        query = query.filter(SourceFile.text_extract_status == selected_status)

    items = query.order_by(SourceFile.id.desc()).limit(200).all()
    if archive_category:
        items = [
            item
            for item in items
            if (load_archive_metadata(item) or {}).get("archive_category") == archive_category
        ]
    if object_name:
        items = [item for item in items if object_name in (_to_dict(db, item).get("object_names") or [])]
    return [_to_dict(db, item) for item in items]


@router.get("/{file_id}")
def get_source_file(file_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(SourceFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="文件不存在")
    data = _to_dict(db, item)
    data["extracted_text"] = item.extracted_text
    return data


@router.post("/{file_id}/bind-counterparty")
def bind_file_counterparty(file_id: int, payload: BindCounterpartyRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
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


@router.patch("/{file_id}/bind-ledger")
def bind_file_ledger(file_id: int, payload: BindLedgerRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """将文件绑定到账簿，或从账簿解绑"""
    item = db.get(SourceFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="文件不存在")
    item.ledger_id = payload.ledger_id
    db.commit()
    db.refresh(item)
    return _to_dict(db, item)


@router.patch("/{file_id}")
def update_source_file(file_id: int, payload: UpdateFileRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """更新文件信息（文件名、文件类型、备注）"""
    item = db.get(SourceFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="文件不存在")
    if payload.filename is not None:
        item.filename = payload.filename
    if payload.file_type is not None:
        item.file_type = payload.file_type
    if payload.notes is not None:
        item.notes = payload.notes
    db.commit()
    db.refresh(item)
    return _to_dict(db, item)


@router.delete("/{file_id}")
def delete_source_file(file_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """删除文件记录"""
    item = db.get(SourceFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="文件不存在")
    db.delete(item)
    db.commit()
    return {"deleted": file_id, "message": "文件已删除"}
