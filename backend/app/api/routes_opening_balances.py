from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import OpeningBalance
from app.db.session import get_db
from app.schemas.money import MoneyField
from app.services.basic_data import opening_balance_service

router = APIRouter(prefix="/api/opening-balances", tags=["opening-balances"])


class OpeningBalanceUpsert(BaseModel):
    organization_id: int
    period_id: int
    ledger_id: int | None = None
    account_code: str
    debit_balance: MoneyField = Decimal("0.00")
    credit_balance: MoneyField = Decimal("0.00")
    currency: str = "CNY"
    notes: str | None = None


class BulkItem(BaseModel):
    account_code: str
    debit_balance: MoneyField = Decimal("0.00")
    credit_balance: MoneyField = Decimal("0.00")
    currency: str = "CNY"
    notes: str | None = None


class BulkUpsertPayload(BaseModel):
    organization_id: int
    period_id: int
    ledger_id: int | None = None
    items: list[BulkItem]


def _to_dict(item: OpeningBalance) -> dict[str, Any]:
    return {
        "id": item.id,
        "organization_id": item.organization_id,
        "ledger_id": item.ledger_id,
        "period_id": item.period_id,
        "account_code": item.account_code,
        "debit_balance": item.debit_balance,
        "credit_balance": item.credit_balance,
        "currency": item.currency,
        "notes": item.notes,
    }


@router.get("")
def list_opening_balances(
    organization_id: int,
    period_id: int,
    ledger_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    items = opening_balance_service.list_by_period(db, organization_id, period_id, ledger_id)
    return [_to_dict(i) for i in items]


@router.post("")
def upsert_opening_balance(payload: OpeningBalanceUpsert, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        record = opening_balance_service.upsert(
            db,
            organization_id=payload.organization_id,
            period_id=payload.period_id,
            account_code=payload.account_code,
            debit_balance=payload.debit_balance,
            credit_balance=payload.credit_balance,
            currency=payload.currency,
            notes=payload.notes,
            ledger_id=payload.ledger_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_dict(record)


@router.post("/bulk")
def bulk_upsert(payload: BulkUpsertPayload, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    try:
        items = opening_balance_service.bulk_upsert(
            db,
            organization_id=payload.organization_id,
            period_id=payload.period_id,
            items=[item.model_dump() for item in payload.items],
            ledger_id=payload.ledger_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_to_dict(i) for i in items]


@router.delete("/{balance_id}")
def delete_opening_balance(balance_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    ok = opening_balance_service.delete_one(db, balance_id)
    if not ok:
        raise HTTPException(status_code=404, detail="期初余额不存在")
    return {"deleted": balance_id}


@router.get("/trial-balance")
def get_trial_balance(
    organization_id: int,
    period_id: int,
    ledger_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return opening_balance_service.trial_balance(db, organization_id, period_id, ledger_id)
