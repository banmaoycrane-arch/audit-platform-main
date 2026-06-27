"""审计协作通知服务。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditNotification


def _serialize(notification: AuditNotification) -> dict[str, Any]:
    return {
        "id": notification.id,
        "recipient_user_id": notification.recipient_user_id,
        "actor_user_id": notification.actor_user_id,
        "event_type": notification.event_type,
        "target_type": notification.target_type,
        "target_id": notification.target_id,
        "title": notification.title,
        "content": notification.content,
        "is_read": notification.is_read,
        "project_id": notification.project_id,
        "ledger_id": notification.ledger_id,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
    }


def create_notification(
    db: Session,
    *,
    recipient_user_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    target_type: str,
    target_id: int,
    title: str,
    content: str | None = None,
    project_id: int | None = None,
    ledger_id: int | None = None,
) -> dict[str, Any] | None:
    if recipient_user_id is None:
        return None
    if actor_user_id is not None and recipient_user_id == actor_user_id:
        return None

    notification = AuditNotification(
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        title=title,
        content=content,
        project_id=project_id,
        ledger_id=ledger_id,
        created_at=datetime.utcnow(),
    )
    db.add(notification)
    db.flush()
    return _serialize(notification)


def create_notifications(
    db: Session,
    *,
    recipient_user_ids: list[int | None],
    actor_user_id: int | None,
    event_type: str,
    target_type: str,
    target_id: int,
    title: str,
    content: str | None = None,
    project_id: int | None = None,
    ledger_id: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for recipient_user_id in recipient_user_ids:
        if recipient_user_id is None or recipient_user_id in seen:
            continue
        seen.add(recipient_user_id)
        row = create_notification(
            db,
            recipient_user_id=recipient_user_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            title=title,
            content=content,
            project_id=project_id,
            ledger_id=ledger_id,
        )
        if row is not None:
            rows.append(row)
    return rows


def list_notifications(
    db: Session,
    *,
    recipient_user_id: int,
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = db.query(AuditNotification).filter(
        AuditNotification.recipient_user_id == recipient_user_id
    )
    if unread_only:
        query = query.filter(AuditNotification.is_read.is_(False))
    rows = query.order_by(AuditNotification.id.desc()).limit(limit).all()
    return [_serialize(row) for row in rows]


def count_unread_notifications(db: Session, *, recipient_user_id: int) -> int:
    return db.query(AuditNotification).filter(
        AuditNotification.recipient_user_id == recipient_user_id,
        AuditNotification.is_read.is_(False),
    ).count()


def mark_notification_read(
    db: Session,
    *,
    notification_id: int,
    recipient_user_id: int,
) -> dict[str, Any]:
    notification = db.query(AuditNotification).filter(
        AuditNotification.id == notification_id,
        AuditNotification.recipient_user_id == recipient_user_id,
    ).first()
    if notification is None:
        raise ValueError("通知不存在")
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.commit()
    db.refresh(notification)
    return _serialize(notification)


def mark_all_read(db: Session, *, recipient_user_id: int) -> int:
    rows = db.query(AuditNotification).filter(
        AuditNotification.recipient_user_id == recipient_user_id,
        AuditNotification.is_read.is_(False),
    ).all()
    now = datetime.utcnow()
    for row in rows:
        row.is_read = True
        row.read_at = now
    db.commit()
    return len(rows)
