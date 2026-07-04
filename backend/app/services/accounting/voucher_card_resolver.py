# -*- coding: utf-8 -*-
"""
凭证聚合查询中 voucher_id / status 字段解析工具。

业务场景：现有 accounting_entries 表未强制关联 vouchers.id，但已通过 voucher_no + voucher_date
逻辑上形成凭证组。在列表页需要展示 voucher_id 和 status 以支持编辑/入账按钮。
政策依据：凭证状态由 Voucher 主表或分录行状态综合决定。

创建日期：2026-07-01
"""
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Voucher


def _resolve_voucher_status_from_entries(entries: list[Any]) -> str:
    """
    根据分录行状态推断凭证状态。

    业务逻辑：
    - 任一分录 post_status='posted' 则凭证状态为 'posted'
    - 任一分录 review_status='verified' 或 'ready' 且未过账，则为 'verified'
    - 否则为 'draft'
    """
    has_posted = any(
        getattr(entry, "post_status", None) == "posted" for entry in entries
    )
    if has_posted:
        return "posted"

    has_verified = any(
        getattr(entry, "review_status", None) in {"verified", "ready"}
        for entry in entries
    )
    if has_verified:
        return "verified"

    return "draft"


def _resolve_voucher_id_from_entries(
    db: Session,
    ledger_id: int,
    voucher_no: str | None,
    voucher_date: date | None,
    entries: list[Any],
) -> int | None:
    """
    解析凭证组对应的 Voucher 主表 ID。

    业务逻辑：
    - 优先使用 AccountingEntry.voucher_id 外键
    - 如果分录行未设置 voucher_id，则根据 voucher_no + voucher_date 查询 Voucher 表
    """
    for entry in entries:
        voucher_id = getattr(entry, "voucher_id", None)
        if voucher_id:
            return int(voucher_id)

    if voucher_no and voucher_date:
        voucher = (
            db.query(Voucher)
            .filter(
                Voucher.ledger_id == ledger_id,
                Voucher.voucher_no == voucher_no,
                Voucher.voucher_date == voucher_date,
            )
            .first()
        )
        if voucher:
            return voucher.id
    return None


def resolve_voucher_card_fields(
    db: Session,
    ledger_id: int,
    voucher_no: str | None,
    voucher_date: date | None,
    entries: list[Any],
) -> tuple[int | None, str]:
    """
    解析 VoucherCard 所需的 voucher_id 和 status。

    返回值：
        (voucher_id, status)
    """
    voucher_id = _resolve_voucher_id_from_entries(
        db, ledger_id, voucher_no, voucher_date, entries
    )
    status = _resolve_voucher_status_from_entries(entries)
    return voucher_id, status


def resolve_voucher_card_fields_from_slim_rows(
    db: Session,
    ledger_id: int,
    voucher_no: str | None,
    voucher_date: date | None,
    rows: list[Any],
) -> tuple[int | None, str]:
    """
    在仅加载 slim rows（无 ORM 对象）时解析 voucher_id 和 status。

    业务逻辑：
    - slim rows 不包含 review_status / post_status，因此统一查询 Voucher 表
    """
    if voucher_no and voucher_date:
        voucher = (
            db.query(Voucher)
            .filter(
                Voucher.ledger_id == ledger_id,
                Voucher.voucher_no == voucher_no,
                Voucher.voucher_date == voucher_date,
            )
            .first()
        )
        if voucher:
            return voucher.id, voucher.status
    return None, "draft"
