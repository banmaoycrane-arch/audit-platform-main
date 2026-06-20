from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import OpeningBalance
from app.db.session import get_db
from app.services import opening_balance_service

router = APIRouter(prefix="/api/opening-balances", tags=["opening-balances"])


class OpeningBalanceUpsert(BaseModel):
    organization_id: int
    period_id: int
    account_code: str
    debit_balance: float = 0
    credit_balance: float = 0
    currency: str = "CNY"
    notes: str | None = None


class BulkItem(BaseModel):
    account_code: str
    debit_balance: float = 0
    credit_balance: float = 0
    currency: str = "CNY"
    notes: str | None = None


class BulkUpsertPayload(BaseModel):
    organization_id: int
    period_id: int
    items: list[BulkItem]


def _to_dict(item: OpeningBalance) -> dict[str, Any]:
    return {
        "id": item.id,
        "organization_id": item.organization_id,
        "period_id": item.period_id,
        "account_code": item.account_code,
        "debit_balance": float(item.debit_balance or 0),
        "credit_balance": float(item.credit_balance or 0),
        "currency": item.currency,
        "notes": item.notes,
    }


@router.get("")
def list_opening_balances(
    organization_id: int,
    period_id: int,
    db: Session = Depends(get_db),
) -> list[dict]:
    items = opening_balance_service.list_by_period(db, organization_id, period_id)
    return [_to_dict(i) for i in items]


@router.post("")
def upsert_opening_balance(payload: OpeningBalanceUpsert, db: Session = Depends(get_db)) -> dict:
    record = opening_balance_service.upsert(
        db,
        organization_id=payload.organization_id,
        period_id=payload.period_id,
        account_code=payload.account_code,
        debit_balance=payload.debit_balance,
        credit_balance=payload.credit_balance,
        currency=payload.currency,
        notes=payload.notes,
    )
    return _to_dict(record)


@router.post("/bulk")
def bulk_upsert(payload: BulkUpsertPayload, db: Session = Depends(get_db)) -> list[dict]:
    items = opening_balance_service.bulk_upsert(
        db,
        organization_id=payload.organization_id,
        period_id=payload.period_id,
        items=[item.model_dump() for item in payload.items],
    )
    return [_to_dict(i) for i in items]


@router.delete("/{balance_id}")
def delete_opening_balance(balance_id: int, db: Session = Depends(get_db)) -> dict:
    ok = opening_balance_service.delete_one(db, balance_id)
    if not ok:
        raise HTTPException(status_code=404, detail="期初余额不存在")
    return {"deleted": balance_id}


@router.get("/trial-balance")
def get_trial_balance(
    organization_id: int,
    period_id: int,
    db: Session = Depends(get_db),
) -> dict:
    return opening_balance_service.trial_balance(db, organization_id, period_id)
