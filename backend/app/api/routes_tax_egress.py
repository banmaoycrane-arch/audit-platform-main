# -*- coding: utf-8 -*-
"""税务城市出口 IP 池 API。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.tax.tax_egress_service import (
    create_binding,
    get_pool_overview,
    list_bindings,
    list_rotation_events,
    rotate_binding,
    start_tax_session,
)

router = APIRouter(prefix="/api/tax/egress", tags=["tax-egress"])


class CreateBindingIn(BaseModel):
    taxpayer_id: str = Field(..., min_length=15, max_length=32)
    taxpayer_name: str = Field(..., min_length=2, max_length=200)
    city_code: str = Field(..., min_length=6, max_length=12)


class RotateBindingIn(BaseModel):
    reason: str | None = Field(None, max_length=500)


@router.get("/pools")
def pools_overview(
    city_code: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    return get_pool_overview(db, city_code=city_code)


@router.get("/bindings")
def bindings_list(
    city_code: str | None = Query(None),
    ledger_id: int | None = Depends(get_current_ledger),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    items = list_bindings(db, ledger_id=ledger_id, city_code=city_code)
    return {"items": items}


@router.post("/bindings")
def bindings_create(
    payload: CreateBindingIn,
    ledger_id: int | None = Depends(get_current_ledger),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return create_binding(
            db,
            taxpayer_id=payload.taxpayer_id,
            taxpayer_name=payload.taxpayer_name,
            city_code=payload.city_code,
            ledger_id=ledger_id,
            team_id=current_user.team_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bindings/{binding_id}/rotate")
def bindings_rotate(
    binding_id: int,
    payload: RotateBindingIn | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    try:
        return rotate_binding(
            db,
            binding_id,
            trigger_code="T5_manual_admin",
            reason_detail=(payload.reason if payload else None) or "管理员手动轮换",
            created_by=current_user.username or f"user:{current_user.id}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bindings/{binding_id}/sessions")
def bindings_start_session(
    binding_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    try:
        return start_tax_session(db, binding_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/rotation-events")
def rotation_events(
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    return {"items": list_rotation_events(db, limit=limit)}
