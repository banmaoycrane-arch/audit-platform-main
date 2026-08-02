# -*- coding: utf-8 -*-
"""
经济事件工单服务层。

业务场景：创建/查询/推进事件工单，挂分录与证据，记录步骤日志。
会计口径：事件不存借贷金额，display_amount 仅展示用，以关联分录汇总为准。
创建日期：2026-08-01
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AccountingEntry,
    EconomicEvent,
    EconomicEventEntry,
    EconomicEventFile,
    EconomicEventStep,
    SourceFile,
)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 状态机允许的迁移边
_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"collecting", "cancelled"},
    "collecting": {"pending_review", "cancelled", "failed"},
    "pending_review": {"pending_post", "collecting", "failed"},
    "pending_post": {"posted", "pending_review", "failed"},
    "posted": {"closed"},
    "closed": set(),  # 终态
    "failed": {"collecting", "draft", "cancelled"},
    "cancelled": set(),  # 终态
}

_VALID_STATUSES = set(_TRANSITIONS.keys())


def _generate_event_no(db: Session, ledger_id: int) -> str:
    """生成事件编号：E-{ledger_id}-{yyMMdd}-{seq3}。"""
    today = _utc_now_naive()
    prefix = f"E-{ledger_id}-{today.strftime('%y%m%d')}-"
    count = db.query(EconomicEvent).filter(EconomicEvent.event_no.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:03d}"


def _next_sequence(db: Session, event_id: int) -> int:
    max_seq = db.query(func.max(EconomicEventStep.sequence)).filter(
        EconomicEventStep.event_id == event_id
    ).scalar()
    return (max_seq or 0) + 1


def _log_step(
    db: Session,
    event_id: int,
    step_code: str,
    step_name: str,
    *,
    actor_user_id: int | None = None,
    actor_type: str = "user",
    api_name: str | None = None,
    payload_digest: str | None = None,
    result_summary: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
) -> EconomicEventStep:
    step = EconomicEventStep(
        event_id=event_id,
        sequence=_next_sequence(db, event_id),
        step_code=step_code,
        step_name=step_name,
        api_name=api_name,
        payload_digest=payload_digest,
        result_summary=result_summary,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        model_provider=model_provider,
        model_name=model_name,
        from_status=from_status,
        to_status=to_status,
        created_at=_utc_now_naive(),
    )
    db.add(step)
    db.flush()
    return step


def create_event(
    db: Session,
    ledger_id: int,
    title: str,
    *,
    event_type: str = "manual",
    occurred_on: Any | None = None,
    summary: str | None = None,
    source: str = "manual",
    source_id: int | None = None,
    created_by: int | None = None,
    assignee_user_id: int | None = None,
) -> EconomicEvent:
    """创建草稿事件工单。"""
    event = EconomicEvent(
        event_no=_generate_event_no(db, ledger_id),
        ledger_id=ledger_id,
        title=title,
        event_type=event_type,
        status="draft",
        occurred_on=occurred_on,
        summary=summary,
        source=source,
        source_id=source_id,
        created_by=created_by,
        assignee_user_id=assignee_user_id,
        created_at=_utc_now_naive(),
        updated_at=_utc_now_naive(),
    )
    db.add(event)
    db.flush()
    _log_step(
        db, event.id, "create", "创建事件工单",
        actor_user_id=created_by,
        result_summary=f"事件类型: {event_type}, 来源: {source}",
        to_status="draft",
    )
    db.commit()
    db.refresh(event)
    return event


def get_event(db: Session, event_id: int) -> EconomicEvent | None:
    return db.get(EconomicEvent, event_id)


def list_events(
    db: Session,
    ledger_id: int,
    *,
    status: str | None = None,
    event_type: str | None = None,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[EconomicEvent]:
    """按账簿查询事件列表，支持状态/类型/关键词过滤。"""
    q = db.query(EconomicEvent).filter(EconomicEvent.ledger_id == ledger_id)
    if status:
        if status not in _VALID_STATUSES:
            raise ValueError(f"无效状态: {status}")
        q = q.filter(EconomicEvent.status == status)
    if event_type:
        q = q.filter(EconomicEvent.event_type == event_type)
    if keyword:
        q = q.filter(EconomicEvent.title.ilike(f"%{keyword}%"))
    return q.order_by(EconomicEvent.created_at.desc()).offset(offset).limit(limit).all()


def attach_entry(
    db: Session,
    event_id: int,
    accounting_entry_id: int,
    *,
    relation_type: str = "primary",
    actor_user_id: int | None = None,
) -> EconomicEventEntry:
    """关联分录到事件。"""
    event = db.get(EconomicEvent, event_id)
    if not event:
        raise ValueError("事件不存在")
    entry = db.get(AccountingEntry, accounting_entry_id)
    if not entry:
        raise ValueError("分录不存在")

    existing = db.query(EconomicEventEntry).filter(
        EconomicEventEntry.event_id == event_id,
        EconomicEventEntry.accounting_entry_id == accounting_entry_id,
    ).first()
    if existing:
        return existing

    link = EconomicEventEntry(
        event_id=event_id,
        accounting_entry_id=accounting_entry_id,
        relation_type=relation_type,
        created_at=_utc_now_naive(),
    )
    db.add(link)
    _log_step(
        db, event_id, "attach_entry", "关联分录",
        actor_user_id=actor_user_id,
        result_summary=f"分录ID={accounting_entry_id}, 关系={relation_type}",
    )
    db.commit()
    db.refresh(link)
    return link


def attach_file(
    db: Session,
    event_id: int,
    source_file_id: int,
    *,
    relation_type: str = "evidence",
    actor_user_id: int | None = None,
) -> EconomicEventFile:
    """关联源文件到事件。"""
    event = db.get(EconomicEvent, event_id)
    if not event:
        raise ValueError("事件不存在")
    sf = db.get(SourceFile, source_file_id)
    if not sf:
        raise ValueError("源文件不存在")

    existing = db.query(EconomicEventFile).filter(
        EconomicEventFile.event_id == event_id,
        EconomicEventFile.source_file_id == source_file_id,
    ).first()
    if existing:
        return existing

    link = EconomicEventFile(
        event_id=event_id,
        source_file_id=source_file_id,
        relation_type=relation_type,
        created_at=_utc_now_naive(),
    )
    db.add(link)
    _log_step(
        db, event_id, "attach_file", "关联证据文件",
        actor_user_id=actor_user_id,
        result_summary=f"文件ID={source_file_id}, 关系={relation_type}",
    )
    db.commit()
    db.refresh(link)
    return link


def transition(
    db: Session,
    event_id: int,
    to_status: str,
    *,
    actor_user_id: int | None = None,
    actor_type: str = "user",
    reason: str | None = None,
) -> EconomicEvent:
    """
    推进事件状态，校验状态机允许边。

    E3 人审闸门：Agent 不得将工单推进到 posted / closed；
    pending_post → posted 必须由人工（actor_type=user）确认。
    """
    event = db.get(EconomicEvent, event_id)
    if not event:
        raise ValueError("事件不存在")
    if to_status not in _VALID_STATUSES:
        raise ValueError(f"无效目标状态: {to_status}")
    allowed = _TRANSITIONS.get(event.status, set())
    if to_status not in allowed:
        raise ValueError(f"不允许从 {event.status} 迁移到 {to_status}")

    safe_actor_type = (actor_type or "user").strip() or "user"
    # 【E3 过账闸门】AI 不绕过人工复核：禁止 Agent 过账或关闭
    if safe_actor_type == "agent" and to_status in {"posted", "closed"}:
        raise ValueError(
            "Agent 不得将事件推进到已入账或已关闭；请人工在「待入账」状态确认过账"
        )
    if event.status == "pending_post" and to_status == "posted" and safe_actor_type != "user":
        raise ValueError(
            "过账前强制人审：pending_post → posted 仅允许人工操作（actor_type=user）"
        )

    from_status = event.status
    event.status = to_status
    event.updated_at = _utc_now_naive()
    if to_status == "closed":
        event.closed_at = _utc_now_naive()

    _log_step(
        db, event_id, "transition", f"状态推进: {from_status} → {to_status}",
        actor_user_id=actor_user_id,
        actor_type=safe_actor_type,
        from_status=from_status,
        to_status=to_status,
        result_summary=reason,
    )
    db.commit()
    db.refresh(event)
    return event


def list_steps(db: Session, event_id: int) -> list[EconomicEventStep]:
    return (
        db.query(EconomicEventStep)
        .filter(EconomicEventStep.event_id == event_id)
        .order_by(EconomicEventStep.sequence.asc())
        .all()
    )


def list_entries(db: Session, event_id: int) -> list[EconomicEventEntry]:
    return (
        db.query(EconomicEventEntry)
        .filter(EconomicEventEntry.event_id == event_id)
        .order_by(EconomicEventEntry.id.asc())
        .all()
    )


def list_files(db: Session, event_id: int) -> list[EconomicEventFile]:
    return (
        db.query(EconomicEventFile)
        .filter(EconomicEventFile.event_id == event_id)
        .order_by(EconomicEventFile.id.asc())
        .all()
    )


def compute_display_amount(db: Session, event_id: int) -> Decimal:
    """汇总关联分录的借方金额作为展示金额。"""
    total = db.query(func.sum(AccountingEntry.debit_amount)).join(
        EconomicEventEntry,
        EconomicEventEntry.accounting_entry_id == AccountingEntry.id,
    ).filter(
        EconomicEventEntry.event_id == event_id,
    ).scalar()
    return total or Decimal("0.00")
