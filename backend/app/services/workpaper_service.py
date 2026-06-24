"""工作底稿索引与版本管理服务（Phase C）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import SourceFile, WorkpaperIndex, WorkpaperVersion
from app.services.draft_archive_service import ARCHIVE_CATEGORIES, load_archive_metadata

AUDIT_AREA_BY_MODULE: dict[str, str] = {
    "bank_cash_flow": "货币资金",
    "tax_invoice": "税务",
    "contract_register": "合同",
    "counterparty_ledger": "往来款项",
    "purchase": "采购",
    "sales": "收入",
    "inventory_receipt": "存货",
    "payroll": "薪酬",
    "day_book": "会计记录",
    "accounting_voucher": "会计记录",
    "general": "综合",
}

STATUS_LABELS = {
    "draft": "草稿",
    "submitted": "已提交",
    "reviewed": "已复核",
    "superseded": "已替代",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _audit_area(module_key: str | None, archive_category: str | None = None) -> str:
    if module_key and module_key in AUDIT_AREA_BY_MODULE:
        return AUDIT_AREA_BY_MODULE[module_key]
    if archive_category:
        return archive_category.replace("底稿", "")
    return "综合"


def _next_index_no(db: Session, ledger_id: int, audit_area: str) -> str:
    prefix = {
        "货币资金": "A",
        "往来款项": "B",
        "采购": "C",
        "收入": "D",
        "税务": "E",
        "合同": "F",
        "存货": "G",
        "薪酬": "H",
        "会计记录": "I",
    }.get(audit_area, "Z")
    count = (
        db.query(WorkpaperIndex)
        .filter(WorkpaperIndex.ledger_id == ledger_id, WorkpaperIndex.index_no.like(f"{prefix}%"))
        .count()
    )
    return f"{prefix}{count + 1}"


def _serialize_version(version: WorkpaperVersion, db: Session) -> dict[str, Any]:
    source_file = version.source_file or db.get(SourceFile, version.source_file_id)
    return {
        "id": version.id,
        "workpaper_index_id": version.workpaper_index_id,
        "source_file_id": version.source_file_id,
        "filename": source_file.filename if source_file else None,
        "version_no": version.version_no,
        "status": version.status,
        "status_label": STATUS_LABELS.get(version.status, version.status),
        "prepared_by": version.prepared_by,
        "reviewed_by": version.reviewed_by,
        "change_reason": version.change_reason,
        "supersedes_id": version.supersedes_id,
        "created_at": _iso(version.created_at),
    }


def _serialize_index(index: WorkpaperIndex, db: Session, *, include_versions: bool = True) -> dict[str, Any]:
    versions = sorted(index.versions, key=lambda item: item.id)
    current_version = versions[-1] if versions else None
    return {
        "id": index.id,
        "ledger_id": index.ledger_id,
        "project_id": index.project_id,
        "parent_id": index.parent_id,
        "index_no": index.index_no,
        "title": index.title,
        "audit_area": index.audit_area,
        "archive_path": index.archive_path,
        "source_module_key": index.source_module_key,
        "sort_order": index.sort_order,
        "version_count": len(versions),
        "current_version_no": current_version.version_no if current_version else None,
        "current_status": current_version.status if current_version else None,
        "created_at": _iso(index.created_at),
        "versions": [_serialize_version(item, db) for item in versions] if include_versions else [],
    }


def list_workpaper_indexes(
    db: Session,
    ledger_id: int,
    *,
    project_id: int | None = None,
) -> list[dict[str, Any]]:
    query = db.query(WorkpaperIndex).filter(WorkpaperIndex.ledger_id == ledger_id)
    if project_id is not None:
        query = query.filter(WorkpaperIndex.project_id == project_id)
    rows = query.order_by(WorkpaperIndex.index_no.asc(), WorkpaperIndex.id.asc()).all()
    return [_serialize_index(row, db, include_versions=False) for row in rows]


def get_workpaper_index(db: Session, index_id: int, ledger_id: int) -> dict[str, Any] | None:
    row = (
        db.query(WorkpaperIndex)
        .filter(WorkpaperIndex.id == index_id, WorkpaperIndex.ledger_id == ledger_id)
        .first()
    )
    if row is None:
        return None
    return _serialize_index(row, db, include_versions=True)


def create_index_node(
    db: Session,
    ledger_id: int,
    *,
    title: str,
    audit_area: str | None = None,
    project_id: int | None = None,
    parent_id: int | None = None,
    index_no: str | None = None,
    archive_path: str | None = None,
    source_module_key: str | None = None,
) -> dict[str, Any]:
    area = audit_area or "综合"
    row = WorkpaperIndex(
        ledger_id=ledger_id,
        project_id=project_id,
        parent_id=parent_id,
        index_no=index_no or _next_index_no(db, ledger_id, area),
        title=title,
        audit_area=area,
        archive_path=archive_path,
        source_module_key=source_module_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_index(row, db, include_versions=True)


def _find_index_by_archive_path(db: Session, ledger_id: int, archive_path: str) -> WorkpaperIndex | None:
    return (
        db.query(WorkpaperIndex)
        .filter(WorkpaperIndex.ledger_id == ledger_id, WorkpaperIndex.archive_path == archive_path)
        .first()
    )


def _create_version(
    db: Session,
    *,
    index: WorkpaperIndex,
    source_file: SourceFile,
    version_no: str,
    prepared_by: int | None = None,
    change_reason: str | None = None,
    supersedes: WorkpaperVersion | None = None,
) -> WorkpaperVersion:
    if supersedes is not None:
        supersedes.status = "superseded"
    version = WorkpaperVersion(
        workpaper_index_id=index.id,
        source_file_id=source_file.id,
        version_no=version_no,
        status="draft",
        prepared_by=prepared_by,
        change_reason=change_reason,
        supersedes_id=supersedes.id if supersedes else None,
    )
    db.add(version)
    return version


def register_source_file(
    db: Session,
    ledger_id: int,
    source_file_id: int,
    *,
    prepared_by: int | None = None,
) -> dict[str, Any]:
    source_file = db.get(SourceFile, source_file_id)
    if source_file is None:
        raise ValueError("source file not found")

    file_ledger_id = source_file.ledger_id
    if file_ledger_id is None and source_file.import_job_id:
        from app.db.models import ImportJob

        job = db.get(ImportJob, source_file.import_job_id)
        file_ledger_id = job.ledger_id if job else None
    if file_ledger_id != ledger_id:
        raise ValueError("source file does not belong to ledger")

    archive = load_archive_metadata(source_file)
    module_key = str(archive.get("module_key") if archive else "general")
    audit_area_name = _audit_area(module_key, archive.get("archive_category") if archive else None)
    archive_path = (archive.get("archive_path") if archive else None) or f"source-file/{source_file.id}"
    title = archive.get("document_type_label") if archive else source_file.filename
    if not title:
        title = source_file.filename

    index = _find_index_by_archive_path(db, ledger_id, archive_path) if archive_path else None
    if index is None:
        index = WorkpaperIndex(
            ledger_id=ledger_id,
            project_id=archive.get("project_id") if archive else None,
            index_no=_next_index_no(db, ledger_id, audit_area_name),
            title=str(title),
            audit_area=audit_area_name,
            archive_path=archive_path,
            source_module_key=module_key,
        )
        db.add(index)
        db.flush()
    else:
        existing = (
            db.query(WorkpaperVersion)
            .filter(
                WorkpaperVersion.workpaper_index_id == index.id,
                WorkpaperVersion.source_file_id == source_file.id,
            )
            .first()
        )
        if existing is not None:
            db.refresh(index)
            return _serialize_index(index, db, include_versions=True)

    _create_version(
        db,
        index=index,
        source_file=source_file,
        version_no="1.0",
        prepared_by=prepared_by,
        change_reason="初始归档版本",
    )
    db.commit()
    db.refresh(index)
    return _serialize_index(index, db, include_versions=True)


def revise_workpaper(
    db: Session,
    index_id: int,
    ledger_id: int,
    *,
    source_file_id: int,
    change_reason: str,
    prepared_by: int | None = None,
) -> dict[str, Any]:
    index = (
        db.query(WorkpaperIndex)
        .filter(WorkpaperIndex.id == index_id, WorkpaperIndex.ledger_id == ledger_id)
        .first()
    )
    if index is None:
        raise ValueError("workpaper index not found")

    source_file = db.get(SourceFile, source_file_id)
    if source_file is None:
        raise ValueError("source file not found")

    file_ledger_id = source_file.ledger_id
    if file_ledger_id is None and source_file.import_job_id:
        from app.db.models import ImportJob

        job = db.get(ImportJob, source_file.import_job_id)
        file_ledger_id = job.ledger_id if job else None
    if file_ledger_id != ledger_id:
        raise ValueError("source file does not belong to ledger")

    current = (
        db.query(WorkpaperVersion)
        .filter(WorkpaperVersion.workpaper_index_id == index_id, WorkpaperVersion.status != "superseded")
        .order_by(WorkpaperVersion.id.desc())
        .first()
    )
    next_no = "1.0"
    if current is not None:
        try:
            major, minor = current.version_no.split(".", 1)
            next_no = f"{major}.{int(minor) + 1}"
        except (ValueError, AttributeError):
            next_no = f"{current.version_no}.1"

    _create_version(
        db,
        index=index,
        source_file=source_file,
        version_no=next_no,
        prepared_by=prepared_by,
        change_reason=change_reason,
        supersedes=current,
    )
    db.commit()
    db.refresh(index)
    return _serialize_index(index, db, include_versions=True)


def update_version_status(
    db: Session,
    version_id: int,
    ledger_id: int,
    *,
    status: str,
    reviewed_by: int | None = None,
) -> dict[str, Any]:
    if status not in STATUS_LABELS:
        raise ValueError(f"invalid status: {status}")

    version = (
        db.query(WorkpaperVersion)
        .join(WorkpaperIndex, WorkpaperVersion.workpaper_index_id == WorkpaperIndex.id)
        .filter(WorkpaperVersion.id == version_id, WorkpaperIndex.ledger_id == ledger_id)
        .first()
    )
    if version is None:
        raise ValueError("workpaper version not found")

    version.status = status
    if status == "reviewed" and reviewed_by is not None:
        version.reviewed_by = reviewed_by
    db.commit()
    db.refresh(version)
    return _serialize_version(version, db)


def sync_from_archived_files(
    db: Session,
    ledger_id: int,
    *,
    prepared_by: int | None = None,
) -> list[dict[str, Any]]:
    from app.db.models import ImportJob

    files = (
        db.query(SourceFile)
        .outerjoin(ImportJob, SourceFile.import_job_id == ImportJob.id)
        .filter((SourceFile.ledger_id == ledger_id) | (ImportJob.ledger_id == ledger_id))
        .order_by(SourceFile.id.asc())
        .all()
    )
    created: list[dict[str, Any]] = []
    for source_file in files:
        if not load_archive_metadata(source_file):
            continue
        created.append(register_source_file(db, ledger_id, source_file.id, prepared_by=prepared_by))
    return created


def export_workpaper_catalog(db: Session, ledger_id: int) -> dict[str, Any]:
    rows = (
        db.query(WorkpaperIndex)
        .filter(WorkpaperIndex.ledger_id == ledger_id)
        .order_by(WorkpaperIndex.index_no.asc(), WorkpaperIndex.id.asc())
        .all()
    )
    items = [_serialize_index(row, db, include_versions=True) for row in rows]
    return {
        "ledger_id": ledger_id,
        "exported_at": datetime.utcnow().isoformat(),
        "index_count": len(items),
        "version_count": sum(item["version_count"] for item in items),
        "items": items,
    }
