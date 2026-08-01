# -*- coding: utf-8 -*-
"""经济事件工单 API 路由。

前缀：/api/economic-events
能力：创建、列表、详情、挂分录、挂证据、推进状态、步骤日志。
"""
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.shared import economic_event_service as svc

router = APIRouter(prefix="/api/economic-events", tags=["economic-events"])


def require_ledger(ledger_id: int | None = Depends(get_current_ledger)) -> int:
    if ledger_id is None:
        raise HTTPException(status_code=400, detail="请先选择账簿（X-Ledger-Id）")
    return ledger_id


# ---------- Request / Response models ----------

class CreateEventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    event_type: str = Field(default="manual", max_length=80)
    occurred_on: date | None = None
    summary: str | None = None
    source: str = Field(default="manual", max_length=20)
    source_id: int | None = None
    assignee_user_id: int | None = None


class AttachEntryRequest(BaseModel):
    accounting_entry_id: int
    relation_type: str = Field(default="primary", max_length=40)


class AttachFileRequest(BaseModel):
    source_file_id: int
    relation_type: str = Field(default="evidence", max_length=40)


class TransitionRequest(BaseModel):
    to_status: str = Field(min_length=1, max_length=40)
    reason: str | None = None
    actor_type: str = Field(default="user", max_length=40)


class EventStepResponse(BaseModel):
    id: int
    sequence: int
    step_code: str
    step_name: str
    api_name: str | None
    payload_digest: str | None
    result_summary: str | None
    actor_user_id: int | None
    actor_type: str
    model_provider: str | None
    model_name: str | None
    from_status: str | None
    to_status: str | None
    created_at: datetime | None

    class Config:
        from_attributes = True


class EventEntryLinkResponse(BaseModel):
    id: int
    accounting_entry_id: int
    relation_type: str
    created_at: datetime | None

    class Config:
        from_attributes = True


class EventFileLinkResponse(BaseModel):
    id: int
    source_file_id: int
    relation_type: str
    created_at: datetime | None

    class Config:
        from_attributes = True


class EventResponse(BaseModel):
    id: int
    event_no: str
    ledger_id: int
    title: str
    event_type: str
    status: str
    occurred_on: date | None
    summary: str | None
    display_amount: str | None
    currency: str
    source: str
    source_id: int | None
    created_by: int | None
    assignee_user_id: int | None
    closed_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    entry_count: int = 0
    file_count: int = 0

    class Config:
        from_attributes = True


class EventDetailResponse(EventResponse):
    steps: list[EventStepResponse] = []
    entries: list[EventEntryLinkResponse] = []
    files: list[EventFileLinkResponse] = []


# ---------- Helpers ----------

def _to_event_response(event, db: Session) -> EventResponse:
    entry_count = len(svc.list_entries(db, event.id))
    file_count = len(svc.list_files(db, event.id))
    return EventResponse(
        id=event.id,
        event_no=event.event_no,
        ledger_id=event.ledger_id,
        title=event.title,
        event_type=event.event_type,
        status=event.status,
        occurred_on=event.occurred_on,
        summary=event.summary,
        display_amount=str(event.display_amount) if event.display_amount else str(svc.compute_display_amount(db, event.id)),
        currency=event.currency,
        source=event.source,
        source_id=event.source_id,
        created_by=event.created_by,
        assignee_user_id=event.assignee_user_id,
        closed_at=event.closed_at,
        created_at=event.created_at,
        updated_at=event.updated_at,
        entry_count=entry_count,
        file_count=file_count,
    )


# ---------- Endpoints ----------

@router.post("/", response_model=EventResponse, status_code=201)
def create_event(
    body: CreateEventRequest,
    ledger_id: int = Depends(require_ledger),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        event = svc.create_event(
            db,
            ledger_id=ledger_id,
            title=body.title,
            event_type=body.event_type,
            occurred_on=body.occurred_on,
            summary=body.summary,
            source=body.source,
            source_id=body.source_id,
            created_by=user.id,
            assignee_user_id=body.assignee_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_event_response(event, db)


@router.get("/", response_model=list[EventResponse])
def list_events(
    ledger_id: int = Depends(require_ledger),
    status_filter: str | None = Query(None, alias="status"),
    event_type: str | None = Query(None),
    keyword: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        events = svc.list_events(
            db,
            ledger_id=ledger_id,
            status=status_filter,
            event_type=event_type,
            keyword=keyword,
            offset=offset,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [_to_event_response(e, db) for e in events]


@router.get("/{event_id}", response_model=EventDetailResponse)
def get_event(
    event_id: int,
    ledger_id: int = Depends(require_ledger),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = svc.get_event(db, event_id)
    if not event or event.ledger_id != ledger_id:
        raise HTTPException(status_code=404, detail="事件不存在")
    base = _to_event_response(event, db)
    steps = [EventStepResponse.model_validate(s) for s in svc.list_steps(db, event_id)]
    entries = [EventEntryLinkResponse.model_validate(e) for e in svc.list_entries(db, event_id)]
    files = [EventFileLinkResponse.model_validate(f) for f in svc.list_files(db, event_id)]
    return EventDetailResponse(**base.model_dump(), steps=steps, entries=entries, files=files)


@router.post("/{event_id}/entries", response_model=EventEntryLinkResponse, status_code=201)
def attach_entry(
    event_id: int,
    body: AttachEntryRequest,
    ledger_id: int = Depends(require_ledger),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        link = svc.attach_entry(
            db, event_id, body.accounting_entry_id,
            relation_type=body.relation_type,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EventEntryLinkResponse.model_validate(link)


@router.post("/{event_id}/files", response_model=EventFileLinkResponse, status_code=201)
def attach_file(
    event_id: int,
    body: AttachFileRequest,
    ledger_id: int = Depends(require_ledger),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        link = svc.attach_file(
            db, event_id, body.source_file_id,
            relation_type=body.relation_type,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EventFileLinkResponse.model_validate(link)


@router.post("/{event_id}/transition", response_model=EventResponse)
def transition(
    event_id: int,
    body: TransitionRequest,
    ledger_id: int = Depends(require_ledger),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        event = svc.transition(
            db, event_id, body.to_status,
            actor_user_id=user.id,
            actor_type=body.actor_type,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_event_response(event, db)


@router.get("/{event_id}/steps", response_model=list[EventStepResponse])
def list_steps(
    event_id: int,
    ledger_id: int = Depends(require_ledger),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = svc.get_event(db, event_id)
    if not event or event.ledger_id != ledger_id:
        raise HTTPException(status_code=404, detail="事件不存在")
    return [EventStepResponse.model_validate(s) for s in svc.list_steps(db, event_id)]
