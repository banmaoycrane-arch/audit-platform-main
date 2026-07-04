from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, BankAccount, BankTransaction


def list_accounts(db: Session, ledger_id: int) -> list[BankAccount]:
    return (
        db.query(BankAccount)
        .filter(BankAccount.ledger_id == ledger_id, BankAccount.is_active.is_(True))
        .order_by(BankAccount.id.asc())
        .all()
    )


def create_account(
    db: Session,
    *,
    ledger_id: int,
    bank_name: str,
    account_no: str,
    account_name: str,
    coa_account_code: str = "1002",
    opening_balance: Decimal | str | float | int = Decimal("0.00"),
) -> BankAccount:
    opening_balance_decimal = Decimal(str(opening_balance)).quantize(Decimal("0.01"))
    account = BankAccount(
        ledger_id=ledger_id,
        bank_name=bank_name,
        account_no=account_no,
        account_name=account_name,
        coa_account_code=coa_account_code or "1002",
        opening_balance=opening_balance_decimal,
        current_balance=opening_balance_decimal,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def create_transaction(
    db: Session,
    *,
    bank_account_id: int,
    ledger_id: int,
    transaction_date: date,
    direction: str,
    amount: Decimal | str | float | int,
    summary: str | None = None,
    counterparty: str | None = None,
) -> BankTransaction:
    if direction not in {"in", "out"}:
        raise ValueError("direction must be in or out")

    amount_decimal = Decimal(str(amount)).quantize(Decimal("0.01"))
    if amount_decimal <= 0:
        raise ValueError("amount must be positive")

    account = db.query(BankAccount).filter(BankAccount.id == bank_account_id).first()
    if not account or account.ledger_id != ledger_id:
        raise ValueError("bank account not found for ledger")

    signed_delta = amount_decimal if direction == "in" else -amount_decimal
    current_balance = account.current_balance or Decimal("0.00")
    account.current_balance = (current_balance + signed_delta).quantize(Decimal("0.01"))

    txn = BankTransaction(
        bank_account_id=bank_account_id,
        ledger_id=ledger_id,
        transaction_date=transaction_date,
        direction=direction,
        amount=amount_decimal,
        summary=summary,
        counterparty=counterparty,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def list_transactions(db: Session, ledger_id: int, status: str | None = None) -> list[BankTransaction]:
    query = db.query(BankTransaction).filter(BankTransaction.ledger_id == ledger_id)
    if status:
        query = query.filter(BankTransaction.reconciliation_status == status)
    return query.order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc()).all()


def _entry_amount(entry: AccountingEntry) -> Decimal:
    debit = entry.debit_amount or Decimal("0.00")
    credit = entry.credit_amount or Decimal("0.00")
    if debit > 0:
        return debit
    return credit


def _entry_direction(entry: AccountingEntry) -> str:
    return "in" if (entry.debit_amount or Decimal("0.00")) > 0 else "out"


def get_ledger_bank_entries(db: Session, ledger_id: int) -> list[AccountingEntry]:
    return (
        db.query(AccountingEntry)
        .filter(
            AccountingEntry.ledger_id == ledger_id,
            AccountingEntry.account_code.isnot(None),
            AccountingEntry.account_code.like("1002%"),
        )
        .order_by(AccountingEntry.voucher_date.asc(), AccountingEntry.id.asc())
        .all()
    )


def get_summary(db: Session, ledger_id: int) -> dict[str, Any]:
    accounts = list_accounts(db, ledger_id)
    unmatched = list_transactions(db, ledger_id, status="unmatched")
    return {
        "account_count": len(accounts),
        "unreconciled_count": len(unmatched),
        "total_balance": sum((account.current_balance or Decimal("0.00")) for account in accounts),
    }


def auto_reconcile(db: Session, ledger_id: int, *, date_tolerance_days: int = 3) -> dict[str, Any]:
    unmatched_txns = list_transactions(db, ledger_id, status="unmatched")
    bank_entries = get_ledger_bank_entries(db, ledger_id)
    matched_entry_ids = {
        txn.matched_entry_id
        for txn in db.query(BankTransaction)
        .filter(
            BankTransaction.ledger_id == ledger_id,
            BankTransaction.matched_entry_id.isnot(None),
        )
        .all()
    }

    matches: list[dict[str, Any]] = []
    for txn in unmatched_txns:
        txn_amount = Decimal(str(txn.amount or 0)).quantize(Decimal("0.01"))
        best_entry: AccountingEntry | None = None
        best_delta = date_tolerance_days + 1

        for entry in bank_entries:
            if entry.id in matched_entry_ids:
                continue
            entry_amount = _entry_amount(entry)
            if abs(entry_amount - txn_amount) > Decimal("0.01"):
                continue
            if _entry_direction(entry) != txn.direction:
                continue
            if not entry.voucher_date:
                continue
            delta = abs((entry.voucher_date - txn.transaction_date).days)
            if delta <= date_tolerance_days and delta < best_delta:
                best_entry = entry
                best_delta = delta

        if best_entry is None:
            continue

        txn.reconciliation_status = "matched"
        txn.matched_entry_id = best_entry.id
        matched_entry_ids.add(best_entry.id)
        matches.append(
            {
                "transaction_id": txn.id,
                "entry_id": best_entry.id,
                "amount": str(txn_amount.quantize(Decimal("0.00"))),
                "transaction_date": str(txn.transaction_date),
                "voucher_date": str(best_entry.voucher_date),
            }
        )

    db.commit()
    remaining_unmatched = list_transactions(db, ledger_id, status="unmatched")
    unmatched_entries = [
        {
            "id": entry.id,
            "voucher_no": entry.voucher_no,
            "voucher_date": str(entry.voucher_date) if entry.voucher_date else None,
            "summary": entry.summary,
            "amount": str(_entry_amount(entry).quantize(Decimal("0.00"))),
            "direction": _entry_direction(entry),
        }
        for entry in bank_entries
        if entry.id not in matched_entry_ids
    ]

    return {
        "matched_count": len(matches),
        "matches": matches,
        "unmatched_transactions": [
            {
                "id": txn.id,
                "transaction_date": str(txn.transaction_date),
                "amount": str((txn.amount or Decimal("0.00")).quantize(Decimal("0.00"))),
                "direction": txn.direction,
                "summary": txn.summary,
            }
            for txn in remaining_unmatched
        ],
        "unmatched_entries": unmatched_entries,
    }
