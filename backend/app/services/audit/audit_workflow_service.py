"""审计程序工作流编排服务（Phase D）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditProcedureRun, ProjectWorkflowConfig, WorkpaperIndex, WorkpaperVersion
from app.services.doc_parsing.draft_archive_service import resolve_project_for_ledger

PROCEDURE_CATALOG: dict[str, dict[str, Any]] = {
    "counterparty_confirmation": {
        "label": "往来函证",
        "entity_type": "counterparty_confirmation",
        "workpaper_hint": "B 往来款项",
    },
    "bank_reconciliation": {
        "label": "银行调节",
        "entity_type": "bank_reconciliation",
        "workpaper_hint": "A 货币资金",
    },
    "purchase_three_way_match": {
        "label": "采购三单匹配",
        "entity_type": "purchase_match",
        "workpaper_hint": "C 采购与付款",
    },
}

MODULE_PROCEDURE_MAP: dict[str, list[str]] = {
    "bank_cash_flow": ["bank_reconciliation"],
    "counterparty_ledger": ["counterparty_confirmation"],
    "purchase": ["purchase_three_way_match"],
    "contract_register": ["purchase_three_way_match"],
}

DEFAULT_ENABLED_PROCEDURES = list(PROCEDURE_CATALOG.keys())

STATUS_LABELS = {
    "planned": "待启动",
    "initiated": "已启动",
    "awaiting_evidence": "待证据",
    "in_review": "复核中",
    "concluded": "已结论",
    "exception": "有异常",
}

TRANSITIONS: dict[str, dict[str, list[str]]] = {
    "counterparty_confirmation": {
        "planned": ["initiated"],
        "initiated": ["awaiting_evidence"],
        "awaiting_evidence": ["in_review"],
        "in_review": ["concluded", "exception"],
        "exception": ["in_review", "concluded"],
    },
    "bank_reconciliation": {
        "planned": ["initiated", "in_review"],
        "initiated": ["in_review"],
        "in_review": ["concluded", "exception"],
        "exception": ["in_review", "concluded"],
    },
    "purchase_three_way_match": {
        "planned": ["initiated", "in_review"],
        "initiated": ["in_review"],
        "in_review": ["concluded", "exception"],
        "exception": ["in_review", "concluded"],
    },
}

ACTION_TO_STATUS: dict[str, str] = {
    "start": "initiated",
    "send": "awaiting_evidence",
    "receive": "in_review",
    "conclude": "concluded",
    "flag_exception": "exception",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _default_config(project_id: int) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "granularity": "standard",
        "enabled_procedures": DEFAULT_ENABLED_PROCEDURES,
        "auto_link_workpaper": True,
        "created_at": None,
        "updated_at": None,
    }


def get_workflow_config(db: Session, project_id: int) -> dict[str, Any]:
    row = db.query(ProjectWorkflowConfig).filter(ProjectWorkflowConfig.project_id == project_id).first()
    if row is None:
        return _default_config(project_id)
    return {
        "project_id": row.project_id,
        "granularity": row.granularity,
        "enabled_procedures": row.enabled_procedures or DEFAULT_ENABLED_PROCEDURES,
        "auto_link_workpaper": row.auto_link_workpaper,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def upsert_workflow_config(
    db: Session,
    project_id: int,
    *,
    granularity: str | None = None,
    enabled_procedures: list[str] | None = None,
    auto_link_workpaper: bool | None = None,
) -> dict[str, Any]:
    row = db.query(ProjectWorkflowConfig).filter(ProjectWorkflowConfig.project_id == project_id).first()
    if row is None:
        row = ProjectWorkflowConfig(project_id=project_id)
        db.add(row)
    if granularity is not None:
        row.granularity = granularity
    if enabled_procedures is not None:
        row.enabled_procedures = enabled_procedures
    if auto_link_workpaper is not None:
        row.auto_link_workpaper = auto_link_workpaper
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return get_workflow_config(db, project_id)


def _find_workpaper_index_for_source(db: Session, ledger_id: int, source_file_id: int | None) -> int | None:
    if source_file_id is None:
        return None
    version = (
        db.query(WorkpaperVersion)
        .join(WorkpaperIndex, WorkpaperVersion.workpaper_index_id == WorkpaperIndex.id)
        .filter(
            WorkpaperVersion.source_file_id == source_file_id,
            WorkpaperIndex.ledger_id == ledger_id,
        )
        .order_by(WorkpaperVersion.id.desc())
        .first()
    )
    return version.workpaper_index_id if version else None


def _serialize_run(run: AuditProcedureRun) -> dict[str, Any]:
    catalog = PROCEDURE_CATALOG.get(run.procedure_key, {})
    allowed = TRANSITIONS.get(run.procedure_key, {}).get(run.status, [])
    return {
        "id": run.id,
        "project_id": run.project_id,
        "ledger_id": run.ledger_id,
        "procedure_key": run.procedure_key,
        "procedure_label": catalog.get("label", run.procedure_key),
        "status": run.status,
        "status_label": STATUS_LABELS.get(run.status, run.status),
        "title": run.title,
        "related_entity_type": run.related_entity_type,
        "related_entity_id": run.related_entity_id,
        "workpaper_index_id": run.workpaper_index_id,
        "source_file_id": run.source_file_id,
        "recommended_by": run.recommended_by,
        "notes": run.notes,
        "allowed_next_statuses": allowed,
        "concluded_at": _iso(run.concluded_at),
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
    }


def list_procedure_runs(
    db: Session,
    ledger_id: int,
    *,
    project_id: int | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    query = db.query(AuditProcedureRun).filter(AuditProcedureRun.ledger_id == ledger_id)
    if project_id is not None:
        query = query.filter(AuditProcedureRun.project_id == project_id)
    if status is not None:
        query = query.filter(AuditProcedureRun.status == status)
    rows = query.order_by(AuditProcedureRun.id.desc()).all()
    return [_serialize_run(row) for row in rows]


def get_procedure_run(db: Session, run_id: int, ledger_id: int) -> dict[str, Any] | None:
    row = (
        db.query(AuditProcedureRun)
        .filter(AuditProcedureRun.id == run_id, AuditProcedureRun.ledger_id == ledger_id)
        .first()
    )
    if row is None:
        return None
    return _serialize_run(row)


def _validate_transition(procedure_key: str, current: str, target: str) -> None:
    allowed = TRANSITIONS.get(procedure_key, {}).get(current, [])
    if target not in allowed:
        raise ValueError(f"cannot transition from {current} to {target}")


def create_procedure_run(
    db: Session,
    ledger_id: int,
    procedure_key: str,
    *,
    title: str | None = None,
    project_id: int | None = None,
    source_file_id: int | None = None,
    related_entity_type: str | None = None,
    related_entity_id: int | None = None,
    recommended_by: str = "manual",
    auto_link_workpaper: bool = True,
) -> dict[str, Any]:
    if procedure_key not in PROCEDURE_CATALOG:
        raise ValueError(f"unknown procedure: {procedure_key}")

    if project_id is None:
        project = resolve_project_for_ledger(db, ledger_id)
        project_id = project.id if project else None

    catalog = PROCEDURE_CATALOG[procedure_key]
    run = AuditProcedureRun(
        project_id=project_id,
        ledger_id=ledger_id,
        procedure_key=procedure_key,
        status="planned",
        title=title or catalog["label"],
        related_entity_type=related_entity_type or catalog["entity_type"],
        related_entity_id=related_entity_id,
        source_file_id=source_file_id,
        recommended_by=recommended_by,
        workpaper_index_id=_find_workpaper_index_for_source(db, ledger_id, source_file_id)
        if auto_link_workpaper
        else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _serialize_run(run)


def advance_procedure_run(
    db: Session,
    run_id: int,
    ledger_id: int,
    *,
    action: str | None = None,
    target_status: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    run = (
        db.query(AuditProcedureRun)
        .filter(AuditProcedureRun.id == run_id, AuditProcedureRun.ledger_id == ledger_id)
        .first()
    )
    if run is None:
        raise ValueError("procedure run not found")

    next_status = target_status or ACTION_TO_STATUS.get(action or "")
    if not next_status:
        raise ValueError("action or target_status required")

    _validate_transition(run.procedure_key, run.status, next_status)
    run.status = next_status
    if notes:
        run.notes = notes
    if next_status == "concluded":
        run.concluded_at = datetime.now(timezone.utc)
    run.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return _serialize_run(run)


def recommend_procedures_from_decomposition(decomposition: dict[str, Any]) -> list[dict[str, Any]]:
    module_keys = [
        str(item.get("module_key"))
        for item in decomposition.get("module_targets", [])
        if item.get("module_key")
    ]
    recommendations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for module_key in module_keys:
        for procedure_key in MODULE_PROCEDURE_MAP.get(module_key, []):
            if procedure_key in seen:
                continue
            seen.add(procedure_key)
            catalog = PROCEDURE_CATALOG[procedure_key]
            recommendations.append(
                {
                    "procedure_key": procedure_key,
                    "procedure_label": catalog["label"],
                    "source_module_key": module_key,
                    "workpaper_index_hint": catalog["workpaper_hint"],
                    "reason": f"底稿语义分解命中模块 {module_key}",
                }
            )
    return recommendations


def create_runs_from_recommendations(
    db: Session,
    ledger_id: int,
    recommendations: list[dict[str, Any]],
    *,
    project_id: int | None = None,
    source_file_id: int | None = None,
) -> list[dict[str, Any]]:
    if project_id is None:
        project = resolve_project_for_ledger(db, ledger_id)
        project_id = project.id if project else None

    config = get_workflow_config(db, project_id) if project_id else {
        "granularity": "standard",
        "enabled_procedures": DEFAULT_ENABLED_PROCEDURES,
        "auto_link_workpaper": True,
    }
    enabled_procs = config.get("enabled_procedures") or DEFAULT_ENABLED_PROCEDURES
    enabled = set(enabled_procs if isinstance(enabled_procs, list) else DEFAULT_ENABLED_PROCEDURES)
    auto_link = bool(config.get("auto_link_workpaper", True))

    created: list[dict[str, Any]] = []
    for item in recommendations:
        procedure_key = item["procedure_key"]
        if procedure_key not in enabled:
            continue
        existing = (
            db.query(AuditProcedureRun)
            .filter(
                AuditProcedureRun.ledger_id == ledger_id,
                AuditProcedureRun.procedure_key == procedure_key,
                AuditProcedureRun.status.notin_(["concluded"]),
            )
            .first()
        )
        if existing is not None:
            created.append(_serialize_run(existing))
            continue
        created.append(
            create_procedure_run(
                db,
                ledger_id,
                procedure_key,
                title=item.get("procedure_label"),
                project_id=project_id,
                source_file_id=source_file_id,
                recommended_by="decomposition",
                auto_link_workpaper=auto_link,
            )
        )
    return created


def sync_confirmation_procedure(
    db: Session,
    ledger_id: int,
    confirmation_id: int,
    confirmation_status: str,
    *,
    difference: float | None = None,
) -> dict[str, Any] | None:
    run = _get_or_create_procedure_run(
        db,
        ledger_id,
        "counterparty_confirmation",
        confirmation_id,
        entity_type="counterparty_confirmation",
    )
    if run is None:
        return None

    status_map = {
        "draft": "planned",
        "sent": "awaiting_evidence",
        "replied": "in_review",
        "exception": "exception",
    }
    target = status_map.get(confirmation_status)
    if target:
        if confirmation_status == "replied" and difference is not None and abs(difference) < 0.01:
            target = "concluded"
        if confirmation_status == "exception":
            target = "exception"
        return _apply_procedure_status(db, run, target)
    return _serialize_run(run)


def _get_or_create_procedure_run(
    db: Session,
    ledger_id: int,
    procedure_key: str,
    entity_id: int,
    *,
    entity_type: str | None = None,
    title: str | None = None,
) -> AuditProcedureRun | None:
    catalog = PROCEDURE_CATALOG.get(procedure_key)
    if catalog is None:
        return None

    entity_type = entity_type or catalog["entity_type"]
    run = (
        db.query(AuditProcedureRun)
        .filter(
            AuditProcedureRun.ledger_id == ledger_id,
            AuditProcedureRun.procedure_key == procedure_key,
            AuditProcedureRun.related_entity_type == entity_type,
            AuditProcedureRun.related_entity_id == entity_id,
        )
        .order_by(AuditProcedureRun.id.desc())
        .first()
    )
    if run is not None:
        return run

    run_data = create_procedure_run(
        db,
        ledger_id,
        procedure_key,
        title=title,
        related_entity_type=entity_type,
        related_entity_id=entity_id,
        recommended_by="system",
    )
    return db.get(AuditProcedureRun, run_data["id"])


def _apply_procedure_status(db: Session, run: AuditProcedureRun, target_status: str) -> dict[str, Any]:
    if run.status != target_status:
        run.status = target_status
        if target_status == "concluded":
            run.concluded_at = datetime.now(timezone.utc)
        run.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
    return _serialize_run(run)


def sync_bank_reconciliation_procedure(
    db: Session,
    ledger_id: int,
    reconciliation_id: int,
    reconciliation_status: str,
) -> dict[str, Any] | None:
    run = _get_or_create_procedure_run(
        db,
        ledger_id,
        "bank_reconciliation",
        reconciliation_id,
        entity_type="bank_reconciliation",
        title="银行调节",
    )
    if run is None:
        return None

    if reconciliation_status == "balanced":
        target = "concluded"
    else:
        target = "in_review"

    return _apply_procedure_status(db, run, target)


def sync_purchase_match_procedure(
    db: Session,
    ledger_id: int,
    contract_id: int,
    match_status: str,
    *,
    title: str | None = None,
) -> dict[str, Any] | None:
    run = _get_or_create_procedure_run(
        db,
        ledger_id,
        "purchase_three_way_match",
        contract_id,
        entity_type="purchase_match",
        title=title or "采购三单匹配",
    )
    if run is None:
        return None

    status_map = {
        "matched": "concluded",
        "incomplete": "in_review",
        "exception": "exception",
    }
    target = status_map.get(match_status, "in_review")
    return _apply_procedure_status(db, run, target)
