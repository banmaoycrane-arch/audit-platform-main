"""期初余额服务。"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod, OpeningBalance


def _period_for_ledger(db: Session, period_id: int, ledger_id: int | None) -> AccountingPeriod | None:
    period = db.get(AccountingPeriod, period_id)
    if not period:
        return None
    if ledger_id is not None and period.ledger_id is not None and period.ledger_id != ledger_id:
        return None
    return period


def list_by_period(
    db: Session,
    organization_id: int,
    period_id: int,
    ledger_id: int | None = None,
) -> list[OpeningBalance]:
    period = _period_for_ledger(db, period_id, ledger_id)
    if not period or period.organization_id != organization_id:
        return []
    query = db.query(OpeningBalance).filter(
        OpeningBalance.organization_id == organization_id,
        OpeningBalance.period_id == period_id,
    )
    return query.order_by(OpeningBalance.account_code).all()


def upsert(
    db: Session,
    organization_id: int,
    period_id: int,
    account_code: str,
    debit_balance: float | Decimal = 0,
    credit_balance: float | Decimal = 0,
    currency: str = "CNY",
    notes: str | None = None,
    ledger_id: int | None = None,
) -> OpeningBalance:
    period = _period_for_ledger(db, period_id, ledger_id)
    if not period or period.organization_id != organization_id:
        raise ValueError("会计期间与账簿不匹配")
    effective_ledger_id = ledger_id or period.ledger_id

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
        record.debit_balance = Decimal(str(debit_balance)) if isinstance(debit_balance, float) else debit_balance
        record.credit_balance = Decimal(str(credit_balance)) if isinstance(credit_balance, float) else credit_balance
        record.currency = currency
        if notes is not None:
            record.notes = notes
        if effective_ledger_id is not None:
            record.ledger_id = effective_ledger_id
        record.updated_at = datetime.now(timezone.utc)
    else:
        record = OpeningBalance(
            organization_id=organization_id,
            ledger_id=effective_ledger_id,
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
    items: Iterable[dict[str, Any]],
    ledger_id: int | None = None,
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
                ledger_id=ledger_id,
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


def trial_balance(
    db: Session,
    organization_id: int,
    period_id: int,
    ledger_id: int | None = None,
) -> dict[str, Any]:
    items = list_by_period(db, organization_id, period_id, ledger_id)
    debit_total = sum((Decimal(str(i.debit_balance or 0)) for i in items), Decimal("0.00"))
    credit_total = sum((Decimal(str(i.credit_balance or 0)) for i in items), Decimal("0.00"))
    diff = debit_total - credit_total
    return {
        "debit_total": str(debit_total.quantize(Decimal("0.00"))),
        "credit_total": str(credit_total.quantize(Decimal("0.00"))),
        "is_balanced": debit_total == credit_total,
        "diff": str(diff.quantize(Decimal("0.00"))),
        "count": len(items),
    }
