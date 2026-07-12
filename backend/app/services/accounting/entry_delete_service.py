"""凭证/分录删除服务 — 按整张凭证事务化删除，避免只删部分分录导致账簿不平衡。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import tuple_
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, BankReconciliationItem, BankTransaction, EntryTag, Voucher


@dataclass(frozen=True)
class VoucherDeleteKey:
    voucher_no: str | None
    voucher_date: date | None


def _voucher_label(key: VoucherDeleteKey) -> str:
    no = key.voucher_no or "无凭证号"
    dt = key.voucher_date.isoformat() if key.voucher_date else "无日期"
    return f"{no}（{dt}）"


def _entries_for_voucher_keys(
    db: Session,
    ledger_id: int,
    keys: list[VoucherDeleteKey],
) -> list[AccountingEntry]:
    if not keys:
        return []
    markers = [(key.voucher_no or None, key.voucher_date) for key in keys]
    return (
        db.query(AccountingEntry)
        .filter(AccountingEntry.ledger_id == ledger_id)
        .filter(tuple_(AccountingEntry.voucher_no, AccountingEntry.voucher_date).in_(markers))
        .order_by(
            AccountingEntry.voucher_no.asc(),
            AccountingEntry.voucher_date.asc(),
            AccountingEntry.entry_line_no.asc(),
            AccountingEntry.id.asc(),
        )
        .all()
    )


def _entries_for_voucher(db: Session, ledger_id: int, key: VoucherDeleteKey) -> list[AccountingEntry]:
    return _entries_for_voucher_keys(db, ledger_id, [key])


def delete_vouchers_transactional(
    db: Session,
    *,
    ledger_id: int,
    voucher_keys: list[VoucherDeleteKey],
) -> dict[str, int]:
    """
    在一个数据库事务内删除多张凭证的全部分录行。
    任一张凭证不存在、已结账或删除失败时整批回滚。
    """
    if not voucher_keys:
        return {"deleted_vouchers": 0, "deleted_entries": 0}

    unique_keys: list[VoucherDeleteKey] = []
    seen: set[tuple[str | None, date | None]] = set()
    for key in voucher_keys:
        marker = (key.voucher_no or None, key.voucher_date)
        if marker in seen:
            continue
        seen.add(marker)
        unique_keys.append(key)

    entry_ids: set[int] = set()
    voucher_ids: set[int] = set()
    vouchers_found = 0
    lines_by_key: dict[tuple[str | None, date | None], list[AccountingEntry]] = {}

    all_lines = _entries_for_voucher_keys(db, ledger_id, unique_keys)
    for line in all_lines:
        lines_by_key.setdefault((line.voucher_no or None, line.voucher_date), []).append(line)

    for key in unique_keys:
        marker = (key.voucher_no or None, key.voucher_date)
        lines = lines_by_key.get(marker, [])
        if not lines:
            raise ValueError(f"凭证不存在或无权删除：{_voucher_label(key)}")
        for line in lines:
            if line.post_status == "posted":
                raise ValueError(f"凭证已结账，不能删除：{_voucher_label(key)}")
            entry_ids.add(line.id)
            if line.voucher_id:
                voucher_ids.add(line.voucher_id)
        vouchers_found += 1

    try:
        if voucher_ids:
            posted_vouchers = (
                db.query(Voucher.id)
                .filter(Voucher.id.in_(voucher_ids), Voucher.status == "posted")
                .count()
            )
            if posted_vouchers:
                raise ValueError("存在已过账凭证，不能删除")
        if entry_ids:
            db.query(BankTransaction).filter(BankTransaction.matched_entry_id.in_(entry_ids)).update(
                {BankTransaction.matched_entry_id: None},
                synchronize_session=False,
            )
            db.query(BankReconciliationItem).filter(BankReconciliationItem.entry_id.in_(entry_ids)).update(
                {BankReconciliationItem.entry_id: None},
                synchronize_session=False,
            )
            db.query(EntryTag).filter(EntryTag.entry_id.in_(entry_ids)).delete(synchronize_session=False)
            deleted_entries = (
                db.query(AccountingEntry)
                .filter(AccountingEntry.id.in_(entry_ids))
                .delete(synchronize_session=False)
            )
        else:
            deleted_entries = 0
        if voucher_ids:
            db.query(Voucher).filter(Voucher.id.in_(voucher_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"deleted_vouchers": vouchers_found, "deleted_entries": deleted_entries}
