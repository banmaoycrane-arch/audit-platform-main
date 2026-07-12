# -*- coding: utf-8 -*-
"""产品埋点 API：记录 MVP 验证事件与 KPI 摘要。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.shared.product_event_service import get_mvp_kpi_summary, record_product_event

router = APIRouter(prefix="/api/product-events", tags=["product-events"])


class ProductEventIn(BaseModel):
    event_name: str = Field(..., max_length=80)
    session_id: str | None = Field(None, max_length=64)
    job_id: int | None = None
    properties: dict[str, Any] | None = None


@router.post("")
def create_product_event(
    payload: ProductEventIn,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    event = record_product_event(
        db,
        event_name=payload.event_name.strip(),
        user_id=current_user.id,
        team_id=current_user.team_id,
        ledger_id=ledger_id,
        job_id=payload.job_id,
        session_id=payload.session_id,
        properties=payload.properties,
    )
    return {"id": event.id, "event_name": event.event_name, "ok": True}


@router.get("/mvp-kpi-summary")
def mvp_kpi_summary(
    days: int = Query(14, ge=1, le=90),
    ledger_id: int | None = Depends(get_current_ledger),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    return get_mvp_kpi_summary(db, days=days, ledger_id=ledger_id)
