"""往来函证控制表服务（Phase B2）。"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Counterparty, CounterpartyConfirmation
from app.services.shared.module_register_service import BALANCE_TYPE_LABELS, list_counterparty_balances

VALID_STATUSES = {"draft", "sent", "replied", "exception"}
ACTIVE_STATUSES = {"draft", "sent"}


def _round_amount(value: float | Decimal | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _balance_key(
    counterparty_id: int | None,
    counterparty_name: str | None,
    balance_type: str,
) -> tuple[int | None, str | None, str]:
    return (counterparty_id, counterparty_name, balance_type)


def _serialize(row: CounterpartyConfirmation, db: Session) -> dict[str, Any]:
    counterparty = db.get(Counterparty, row.counterparty_id) if row.counterparty_id else None
    name = counterparty.name if counterparty else row.counterparty_name
    return {
        "id": row.id,
        "ledger_id": row.ledger_id,
        "counterparty_id": row.counterparty_id,
        "counterparty_name": name,
        "balance_type": row.balance_type,
        "balance_type_label": BALANCE_TYPE_LABELS.get(row.balance_type, row.balance_type),
        "book_balance": _round_amount(row.book_balance),
        "confirmation_amount": _round_amount(row.confirmation_amount),
        "reply_amount": _round_amount(row.reply_amount),
        "difference": _round_amount(row.difference),
        "status": row.status,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "replied_at": row.replied_at.isoformat() if row.replied_at else None,
        "source_file_id": row.source_file_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_confirmations(db: Session, ledger_id: int) -> list[dict[str, Any]]:
    rows = (
        db.query(CounterpartyConfirmation)
        .filter(CounterpartyConfirmation.ledger_id == ledger_id)
        .order_by(CounterpartyConfirmation.id.desc())
        .all()
    )
    return [_serialize(row, db) for row in rows]


def get_confirmation(db: Session, confirmation_id: int, ledger_id: int) -> dict[str, Any] | None:
    row = (
        db.query(CounterpartyConfirmation)
        .filter(
            CounterpartyConfirmation.id == confirmation_id,
            CounterpartyConfirmation.ledger_id == ledger_id,
        )
        .first()
    )
    if row is None:
        return None
    return _serialize(row, db)


def _find_active_confirmation(
    db: Session,
    ledger_id: int,
    key: tuple[int | None, str | None, str],
) -> CounterpartyConfirmation | None:
    counterparty_id, counterparty_name, balance_type = key
    query = db.query(CounterpartyConfirmation).filter(
        CounterpartyConfirmation.ledger_id == ledger_id,
        CounterpartyConfirmation.balance_type == balance_type,
        CounterpartyConfirmation.status.in_(ACTIVE_STATUSES),
    )
    if counterparty_id is not None:
        query = query.filter(CounterpartyConfirmation.counterparty_id == counterparty_id)
    else:
        query = query.filter(
            CounterpartyConfirmation.counterparty_id.is_(None),
            CounterpartyConfirmation.counterparty_name == counterparty_name,
        )
    return query.first()


def create_from_balances(
    db: Session,
    ledger_id: int,
    *,
    counterparty_ids: list[int] | None = None,
    balance_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    balances = list_counterparty_balances(db, ledger_id)
    created: list[CounterpartyConfirmation] = []

    for bucket in balances:
        counterparty_id = bucket.get("counterparty_id")
        if counterparty_ids and counterparty_id not in counterparty_ids:
            continue
        balance_type = bucket["balance_type"]
        if balance_types and balance_type not in balance_types:
            continue

        book_balance = Decimal(str(bucket["total_amount"] or 0)).quantize(Decimal("0.01"))
        if book_balance <= 0:
            continue

        key = _balance_key(counterparty_id, bucket.get("counterparty_name"), balance_type)
        existing = _find_active_confirmation(db, ledger_id, key)
        if existing is not None:
            existing.book_balance = book_balance
            existing.confirmation_amount = book_balance
            created.append(existing)
            continue

        row = CounterpartyConfirmation(
            ledger_id=ledger_id,
            counterparty_id=counterparty_id,
            counterparty_name=bucket.get("counterparty_name"),
            balance_type=balance_type,
            book_balance=book_balance,
            confirmation_amount=book_balance,
            status="draft",
        )
        db.add(row)
        created.append(row)

    db.commit()
    for row in created:
        db.refresh(row)
    return [_serialize(row, db) for row in created]


def _apply_reply_difference(row: CounterpartyConfirmation, reply_amount: Decimal | str | float | int) -> None:
    row.reply_amount = Decimal(str(reply_amount)).quantize(Decimal("0.01"))
    confirmation_amount = row.confirmation_amount or Decimal("0.00")
    difference = (row.reply_amount - confirmation_amount).quantize(Decimal("0.01"))
    row.difference = difference
    row.replied_at = datetime.now(timezone.utc)
    row.status = "exception" if difference != Decimal("0") else "replied"


def update_confirmation(
    db: Session,
    confirmation_id: int,
    ledger_id: int,
    *,
    status: str | None = None,
    confirmation_amount: Decimal | str | float | int | None = None,
    reply_amount: Decimal | str | float | int | None = None,
    source_file_id: int | None = None,
) -> dict[str, Any]:
    row = (
        db.query(CounterpartyConfirmation)
        .filter(
            CounterpartyConfirmation.id == confirmation_id,
            CounterpartyConfirmation.ledger_id == ledger_id,
        )
        .first()
    )
    if row is None:
        raise ValueError("confirmation not found")

    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status}")
        row.status = status
        if status == "sent" and row.sent_at is None:
            row.sent_at = datetime.now(timezone.utc)

    if confirmation_amount is not None:
        row.confirmation_amount = Decimal(str(confirmation_amount)).quantize(Decimal("0.01"))

    if source_file_id is not None:
        row.source_file_id = source_file_id

    if reply_amount is not None:
        _apply_reply_difference(row, reply_amount)

    db.commit()
    db.refresh(row)
    result = _serialize(row, db)
    try:
        from app.services.audit import audit_workflow_service

        audit_workflow_service.sync_confirmation_procedure(
            db,
            ledger_id,
            confirmation_id,
            row.status,
            difference=result.get("difference"),
        )
    except Exception:
        pass
    return result


def record_reply(
    db: Session,
    confirmation_id: int,
    ledger_id: int,
    reply_amount: Decimal | str | float | int,
    *,
    source_file_id: int | None = None,
) -> dict[str, Any]:
    return update_confirmation(
        db,
        confirmation_id,
        ledger_id,
        reply_amount=reply_amount,
        source_file_id=source_file_id,
    )
