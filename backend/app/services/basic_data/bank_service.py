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
    source_sub_code: str | None = None,
    opening_balance: Decimal | str | float | int = Decimal("0.00"),
) -> BankAccount:
    opening_balance_decimal = Decimal(str(opening_balance)).quantize(Decimal("0.01"))
    normalized_sub = (source_sub_code or "").strip() or None
    normalized_no = account_no.strip()
    normalized_name = account_name.strip()
    normalized_bank = bank_name.strip()

    existing: BankAccount | None = None
    if normalized_sub:
        existing = (
            db.query(BankAccount)
            .filter(BankAccount.ledger_id == ledger_id, BankAccount.source_sub_code == normalized_sub)
            .first()
        )
    if existing is None and normalized_no:
        existing = (
            db.query(BankAccount)
            .filter(BankAccount.ledger_id == ledger_id, BankAccount.account_no == normalized_no)
            .first()
        )

    if existing:
        existing.bank_name = normalized_bank
        existing.account_no = normalized_no
        existing.account_name = normalized_name
        existing.coa_account_code = coa_account_code or "1002"
        if normalized_sub:
            existing.source_sub_code = normalized_sub
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    account = BankAccount(
        ledger_id=ledger_id,
        bank_name=normalized_bank,
        account_no=normalized_no,
        account_name=normalized_name,
        coa_account_code=coa_account_code or "1002",
        source_sub_code=normalized_sub,
        opening_balance=opening_balance_decimal,
        current_balance=opening_balance_decimal,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_account(
    db: Session,
    *,
    account_id: int,
    ledger_id: int,
    bank_name: str,
    account_no: str,
    account_name: str,
    coa_account_code: str = "1002",
    source_sub_code: str | None = None,
) -> BankAccount:
    account = (
        db.query(BankAccount)
        .filter(BankAccount.id == account_id, BankAccount.ledger_id == ledger_id)
        .first()
    )
    if account is None:
        raise ValueError("银行账户不存在")

    normalized_sub = (source_sub_code or "").strip() or None
    if normalized_sub:
        conflict = (
            db.query(BankAccount)
            .filter(
                BankAccount.ledger_id == ledger_id,
                BankAccount.source_sub_code == normalized_sub,
                BankAccount.id != account_id,
            )
            .first()
        )
        if conflict:
            raise ValueError(f"来源段「{normalized_sub}」已被其他账户使用")

    account.bank_name = bank_name.strip()
    account.account_no = account_no.strip()
    account.account_name = account_name.strip()
    account.coa_account_code = coa_account_code or "1002"
    account.source_sub_code = normalized_sub
    account.is_active = True
    db.commit()
    db.refresh(account)
    return account


def deactivate_account(db: Session, *, account_id: int, ledger_id: int) -> None:
    """软删除银行账户（误登记时可移除，不影响历史流水）。"""
    account = (
        db.query(BankAccount)
        .filter(BankAccount.id == account_id, BankAccount.ledger_id == ledger_id)
        .first()
    )
    if account is None:
        raise ValueError("银行账户不存在")
    account.is_active = False
    db.commit()


def bulk_import_accounts(
    db: Session,
    *,
    ledger_id: int,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """批量导入开户清单（外部证据层）。"""
    created = 0
    skipped = 0
    errors: list[str] = []
    for idx, record in enumerate(records, start=1):
        bank_name = str(record.get("bank_name") or record.get("开户银行") or "").strip()
        account_no = str(record.get("account_no") or record.get("账号") or "").strip()
        account_name = str(record.get("account_name") or record.get("户名") or "").strip()
        if not bank_name or not account_no:
            errors.append(f"第 {idx} 行缺少银行名称或账号")
            skipped += 1
            continue
        coa_code = str(record.get("coa_account_code") or record.get("关联科目") or "1002").strip() or "1002"
        source_sub_code = str(record.get("source_sub_code") or record.get("来源段") or "").strip() or None
        existing = (
            db.query(BankAccount)
            .filter(
                BankAccount.ledger_id == ledger_id,
                BankAccount.account_no == account_no,
            )
            .first()
        )
        if existing:
            existing.bank_name = bank_name
            existing.account_name = account_name or existing.account_name
            existing.coa_account_code = coa_code
            if source_sub_code:
                existing.source_sub_code = source_sub_code
            skipped += 1
            continue
        opening_balance_decimal = Decimal(str(record.get("opening_balance") or record.get("期初余额") or 0)).quantize(
            Decimal("0.01")
        )
        account = BankAccount(
            ledger_id=ledger_id,
            bank_name=bank_name,
            account_no=account_no,
            account_name=account_name or bank_name,
            coa_account_code=coa_code,
            source_sub_code=source_sub_code,
            opening_balance=opening_balance_decimal,
            current_balance=opening_balance_decimal,
        )
        db.add(account)
        created += 1
    db.commit()
    return {"created": created, "skipped": skipped, "errors": errors}


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
