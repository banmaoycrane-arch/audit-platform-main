"""审计协作通知 API。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
import app.services.audit.audit_notification_service as audit_notification_service

router = APIRouter(prefix="/api/audit/notifications", tags=["audit-notifications"])


class AuditNotificationRead(BaseModel):
    id: int
    recipient_user_id: int
    actor_user_id: int | None = None
    event_type: str
    target_type: str
    target_id: int
    title: str
    content: str | None = None
    is_read: bool
    project_id: int | None = None
    ledger_id: int | None = None
    created_at: str | None = None
    read_at: str | None = None


class AuditNotificationListResponse(BaseModel):
    items: list[AuditNotificationRead]
    unread_count: int


@router.get("", response_model=AuditNotificationListResponse)
def list_my_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditNotificationListResponse:
    items = audit_notification_service.list_notifications(
        db,
        recipient_user_id=current_user.id,
        unread_only=unread_only,
        limit=limit,
    )
    unread_count = audit_notification_service.count_unread_notifications(
        db,
        recipient_user_id=current_user.id,
    )
    return AuditNotificationListResponse(
        items=[AuditNotificationRead.model_validate(item) for item in items],
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read", response_model=AuditNotificationRead)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditNotificationRead:
    try:
        row = audit_notification_service.mark_notification_read(
            db,
            notification_id=notification_id,
            recipient_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AuditNotificationRead.model_validate(row)


@router.post("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int | str]:
    count = audit_notification_service.mark_all_read(db, recipient_user_id=current_user.id)
    return {"status": "success", "updated_count": count}
