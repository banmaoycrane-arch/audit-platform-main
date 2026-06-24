"""银行调节表草稿服务（Phase B1）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import BankAccount, BankReconciliation, BankReconciliationItem, BankTransaction
from app.services import bank_service

ITEM_TYPE_LABELS = {
    "outstanding_deposit": "企业已收、银行未收",
    "outstanding_payment": "企业已付、银行未付",
    "bank_credit_not_in_books": "银行已收、企业未记",
    "bank_debit_not_in_books": "银行已付、企业未记",
}


def _round_amount(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _entry_matches_coa(entry_account_code: str | None, coa_account_code: str) -> bool:
    if not entry_account_code:
        return False
    prefix = coa_account_code.rstrip("%")
    return entry_account_code == prefix or entry_account_code.startswith(prefix)


def compute_book_balance(
    db: Session,
    ledger_id: int,
    coa_account_code: str,
    period_end: date,
) -> float:
    total = Decimal("0")
    for entry in bank_service.get_ledger_bank_entries(db, ledger_id):
        if entry.voucher_date and entry.voucher_date > period_end:
            continue
        if not _entry_matches_coa(entry.account_code, coa_account_code):
            continue
        debit = Decimal(str(entry.debit_amount or 0))
        credit = Decimal(str(entry.credit_amount or 0))
        total += debit - credit
    return _round_amount(total)


def _serialize_item(item: BankReconciliationItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "item_type": item.item_type,
        "item_type_label": ITEM_TYPE_LABELS.get(item.item_type, item.item_type),
        "amount": _round_amount(item.amount),
        "direction": item.direction,
        "bank_transaction_id": item.bank_transaction_id,
        "entry_id": item.entry_id,
        "summary": item.summary,
        "note": item.note,
    }


def _serialize_reconciliation(reconciliation: BankReconciliation) -> dict[str, Any]:
    account = reconciliation.bank_account
    return {
        "id": reconciliation.id,
        "ledger_id": reconciliation.ledger_id,
        "bank_account_id": reconciliation.bank_account_id,
        "bank_name": account.bank_name if account else None,
        "account_no": account.account_no if account else None,
        "period_end": reconciliation.period_end.isoformat(),
        "statement_balance": _round_amount(reconciliation.statement_balance),
        "book_balance": _round_amount(reconciliation.book_balance),
        "adjusted_statement_balance": _round_amount(reconciliation.adjusted_statement_balance),
        "adjusted_book_balance": _round_amount(reconciliation.adjusted_book_balance),
        "difference": _round_amount(reconciliation.difference),
        "status": reconciliation.status,
        "created_at": reconciliation.created_at.isoformat() if reconciliation.created_at else None,
        "items": [_serialize_item(item) for item in reconciliation.items],
    }


def list_reconciliations(db: Session, ledger_id: int) -> list[dict[str, Any]]:
    rows = (
        db.query(BankReconciliation)
        .filter(BankReconciliation.ledger_id == ledger_id)
        .order_by(BankReconciliation.id.desc())
        .all()
    )
    return [_serialize_reconciliation(row) for row in rows]


def get_reconciliation(db: Session, reconciliation_id: int, ledger_id: int) -> dict[str, Any] | None:
    row = (
        db.query(BankReconciliation)
        .filter(
            BankReconciliation.id == reconciliation_id,
            BankReconciliation.ledger_id == ledger_id,
        )
        .first()
    )
    if row is None:
        return None
    return _serialize_reconciliation(row)


def build_draft(
    db: Session,
    ledger_id: int,
    bank_account_id: int,
    period_end: date,
    *,
    statement_balance: float | None = None,
) -> dict[str, Any]:
    account = (
        db.query(BankAccount)
        .filter(BankAccount.id == bank_account_id, BankAccount.ledger_id == ledger_id)
        .first()
    )
    if account is None:
        raise ValueError("bank account not found for ledger")

    reconcile_result = bank_service.auto_reconcile(db, ledger_id)

    stmt_balance = Decimal(str(
        statement_balance if statement_balance is not None else float(account.current_balance or 0)
    ))
    book_balance = Decimal(str(compute_book_balance(db, ledger_id, account.coa_account_code, period_end)))

    outstanding_deposit = Decimal("0")
    outstanding_payment = Decimal("0")
    bank_credit = Decimal("0")
    bank_debit = Decimal("0")
    draft_items: list[dict[str, Any]] = []

    unmatched_txns = (
        db.query(BankTransaction)
        .filter(
            BankTransaction.ledger_id == ledger_id,
            BankTransaction.bank_account_id == bank_account_id,
            BankTransaction.reconciliation_status == "unmatched",
            BankTransaction.transaction_date <= period_end,
        )
        .order_by(BankTransaction.transaction_date.asc(), BankTransaction.id.asc())
        .all()
    )
    for txn in unmatched_txns:
        amount = Decimal(str(txn.amount or 0))
        if txn.direction == "in":
            item_type = "bank_credit_not_in_books"
            bank_credit += amount
        else:
            item_type = "bank_debit_not_in_books"
            bank_debit += amount
        draft_items.append(
            {
                "item_type": item_type,
                "amount": _round_amount(amount),
                "direction": txn.direction,
                "bank_transaction_id": txn.id,
                "entry_id": None,
                "summary": txn.summary,
                "note": None,
            }
        )

    for entry_data in reconcile_result["unmatched_entries"]:
        voucher_date_raw = entry_data.get("voucher_date")
        if voucher_date_raw:
            voucher_date = date.fromisoformat(voucher_date_raw)
            if voucher_date > period_end:
                continue
        amount = Decimal(str(entry_data["amount"]))
        direction = entry_data["direction"]
        if direction == "in":
            item_type = "outstanding_deposit"
            outstanding_deposit += amount
        else:
            item_type = "outstanding_payment"
            outstanding_payment += amount
        draft_items.append(
            {
                "item_type": item_type,
                "amount": _round_amount(amount),
                "direction": direction,
                "bank_transaction_id": None,
                "entry_id": entry_data["id"],
                "summary": entry_data.get("summary"),
                "note": entry_data.get("voucher_no"),
            }
        )

    adjusted_statement = _round_amount(stmt_balance + outstanding_deposit - outstanding_payment)
    adjusted_book = _round_amount(book_balance + bank_credit - bank_debit)
    difference = _round_amount(adjusted_statement - adjusted_book)
    status = "balanced" if abs(difference) < 0.01 else "draft"

    reconciliation = BankReconciliation(
        ledger_id=ledger_id,
        bank_account_id=bank_account_id,
        period_end=period_end,
        statement_balance=_round_amount(stmt_balance),
        book_balance=_round_amount(book_balance),
        adjusted_statement_balance=adjusted_statement,
        adjusted_book_balance=adjusted_book,
        difference=difference,
        status=status,
    )
    db.add(reconciliation)
    db.flush()

    for item_data in draft_items:
        db.add(
            BankReconciliationItem(
                reconciliation_id=reconciliation.id,
                **item_data,
            )
        )

    db.commit()
    db.refresh(reconciliation)
    return _serialize_reconciliation(reconciliation)
