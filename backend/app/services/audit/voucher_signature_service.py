# -*- coding: utf-8 -*-
"""凭证签章链：制单人（序时簿原始）→ 复核人（平级交叉核对）→ 审核人（主管确认）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.models import StagingAccountingEntry, Voucher


def _load_user_display_names(db, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    from app.models.user import User

    rows = db.query(User).filter(User.id.in_(list(user_ids))).all()
    return {
        user.id: (user.username or user.phone or user.email or f"用户{user.id}")
        for user in rows
    }


def enrich_voucher_summaries_with_signature_names(
    db,
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """为凭证摘要列表补充复核人显示名。"""
    user_ids = {
        int(item["cross_reviewed_by_user_id"])
        for item in summaries
        if item.get("cross_reviewed_by_user_id") is not None
    }
    names = _load_user_display_names(db, user_ids)
    for item in summaries:
        uid = item.get("cross_reviewed_by_user_id")
        item["cross_reviewed_by_name"] = names.get(int(uid)) if uid is not None else None
    return summaries


def build_staging_signature_payload(
    db,
    rows: list[StagingAccountingEntry],
) -> dict[str, Any]:
    """构建单张 staging 凭证的签章展示块（Step4 抽屉用）。"""
    sig = signature_from_staging_group(rows)
    uid = sig.get("cross_reviewed_by_user_id")
    names = _load_user_display_names(db, {int(uid)} if uid is not None else set())
    reviewed_at = sig.get("cross_reviewed_at")
    return {
        "source_preparer_name": sig.get("source_preparer_name"),
        "cross_reviewed_by_user_id": uid,
        "cross_reviewed_by_name": names.get(int(uid)) if uid is not None else None,
        "cross_reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
        "approved_by_name": None,
        "approved_at": None,
    }


def extract_source_preparer_name(entry_data: dict[str, Any]) -> str | None:
    """从解析行或 original_row 提取序时簿原始制单人。"""
    for key in ("source_preparer_name", "source_preparer"):
        val = entry_data.get(key)
        if val and str(val).strip():
            return str(val).strip()
    original = entry_data.get("original_row") or {}
    if isinstance(original, dict):
        for key in ("source_preparer_name", "source_preparer", "制单人", "制表人", "经办人", "录入人"):
            val = original.get(key)
            if val and str(val).strip():
                return str(val).strip()
    return None


def stamp_voucher_signatures(
    voucher: Voucher,
    *,
    source_preparer_name: str | None,
    cross_reviewed_by_user_id: int | None,
    cross_reviewed_at: datetime | None,
    approved_by_user_id: int | None,
    approved_at: datetime | None,
) -> None:
    if source_preparer_name:
        voucher.source_preparer_name = source_preparer_name
    if cross_reviewed_by_user_id is not None:
        voucher.cross_reviewed_by_user_id = cross_reviewed_by_user_id
        voucher.cross_reviewed_at = cross_reviewed_at
    if approved_by_user_id is not None:
        voucher.approved_by_user_id = approved_by_user_id
        voucher.approved_at = approved_at or datetime.now(timezone.utc)


def signature_from_staging_group(rows: list[StagingAccountingEntry]) -> dict[str, Any]:
    """从同一凭证的 staging 行聚合签章信息（取首行非空）。"""
    first = rows[0] if rows else None
    if first is None:
        return {}
    preparer = first.source_preparer_name
    if not preparer:
        preparer = extract_source_preparer_name({"original_row": first.original_row or {}})
    return {
        "source_preparer_name": preparer,
        "cross_reviewed_by_user_id": first.cross_reviewed_by_user_id,
        "cross_reviewed_at": first.cross_reviewed_at,
    }
