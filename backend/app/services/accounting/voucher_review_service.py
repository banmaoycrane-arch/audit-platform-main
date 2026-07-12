"""凭证审核服务（类型2：pending → reviewed/posted）。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, Voucher
from app.services.audit.audit_day_book_service import _validate_voucher_balance


def _entries_for_voucher(db: Session, voucher_id: int) -> list[dict]:
    rows = db.query(AccountingEntry).filter(AccountingEntry.voucher_id == voucher_id).all()
    return [
        {
            "debit_amount": row.debit_amount or Decimal("0"),
            "credit_amount": row.credit_amount or Decimal("0"),
        }
        for row in rows
    ]


def review_voucher(db: Session, voucher_id: int) -> Voucher:
    voucher = db.get(Voucher, voucher_id)
    if not voucher:
        raise ValueError("凭证不存在")
    entries = _entries_for_voucher(db, voucher_id)
    if entries:
        is_balanced, _, _, _ = _validate_voucher_balance(entries)
        if not is_balanced:
            raise ValueError("借贷不平衡的凭证不能审核通过")
    voucher.status = "posted"
    db.query(AccountingEntry).filter(AccountingEntry.voucher_id == voucher_id).update(
        {"review_status": "reviewed", "post_status": "posted"},
        synchronize_session=False,
    )
    db.commit()
    db.refresh(voucher)
    return voucher


def review_vouchers_batch(db: Session, voucher_ids: list[int]) -> int:
    reviewed = 0
    for voucher_id in voucher_ids:
        review_voucher(db, voucher_id)
        reviewed += 1
    return reviewed


def unreview_voucher(db: Session, voucher_id: int) -> Voucher:
    voucher = db.get(Voucher, voucher_id)
    if not voucher:
        raise ValueError("凭证不存在")
    voucher.status = "pending"
    db.query(AccountingEntry).filter(AccountingEntry.voucher_id == voucher_id).update(
        {"review_status": "pending", "post_status": "draft"},
        synchronize_session=False,
    )
    db.commit()
    db.refresh(voucher)
    return voucher
