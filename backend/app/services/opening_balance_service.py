"""期初余额服务。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session

from app.db.models import OpeningBalance


def list_by_period(db: Session, organization_id: int, period_id: int) -> list[OpeningBalance]:
    return (
        db.query(OpeningBalance)
        .filter(
            OpeningBalance.organization_id == organization_id,
            OpeningBalance.period_id == period_id,
        )
        .order_by(OpeningBalance.account_code)
        .all()
    )


def upsert(
    db: Session,
    organization_id: int,
    period_id: int,
    account_code: str,
    debit_balance: float | Decimal = 0,
    credit_balance: float | Decimal = 0,
    currency: str = "CNY",
    notes: str | None = None,
) -> OpeningBalance:
    record = (
        db.query(OpeningBalance)
        .filter(
            OpeningBalance.organization_id == organization_id,
            OpeningBalance.period_id == period_id,
            OpeningBalance.account_code == account_code,
        )
        .first()
    )
    if record:
        record.debit_balance = Decimal(str(debit_balance))
        record.credit_balance = Decimal(str(credit_balance))
        record.currency = currency
        if notes is not None:
            record.notes = notes
        record.updated_at = datetime.utcnow()
    else:
        record = OpeningBalance(
            organization_id=organization_id,
            period_id=period_id,
            account_code=account_code,
            debit_balance=Decimal(str(debit_balance)),
            credit_balance=Decimal(str(credit_balance)),
            currency=currency,
            notes=notes,
        )
        db.add(record)
    db.commit()
    db.refresh(record)
    return record


def bulk_upsert(
    db: Session,
    organization_id: int,
    period_id: int,
    items: Iterable[dict],
) -> list[OpeningBalance]:
    persisted: list[OpeningBalance] = []
    for item in items:
        persisted.append(
            upsert(
                db,
                organization_id=organization_id,
                period_id=period_id,
                account_code=item["account_code"],
                debit_balance=item.get("debit_balance", 0),
                credit_balance=item.get("credit_balance", 0),
                currency=item.get("currency", "CNY"),
                notes=item.get("notes"),
            )
        )
    return persisted


def delete_one(db: Session, balance_id: int) -> bool:
    record = db.get(OpeningBalance, balance_id)
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True


def trial_balance(db: Session, organization_id: int, period_id: int) -> dict:
    items = list_by_period(db, organization_id, period_id)
    debit_total = sum(Decimal(str(i.debit_balance or 0)) for i in items)
    credit_total = sum(Decimal(str(i.credit_balance or 0)) for i in items)
    return {
        "debit_total": float(debit_total),
        "credit_total": float(credit_total),
        "is_balanced": debit_total == credit_total,
        "diff": float(debit_total - credit_total),
        "count": len(items),
    }
