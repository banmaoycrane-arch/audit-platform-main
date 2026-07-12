"""维度值与主数据（银行户、往来单位）同步。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import BankAccount, Counterparty
from app.config.tag_category_constants import is_bank_account_category

CATEGORY_COUNTERPARTY_ROLE: dict[str, str] = {
    "customer": "customer",
    "supplier": "supplier",
    "counterparty_object": "other",
}


def lookup_master_display_name(
    db: Session,
    ledger_id: int | None,
    *,
    category_code: str,
    tag_value: str,
    source_sub_code: str | None = None,
    account_code: str | None = None,
) -> str | None:
    """从主数据查找规范全称（确认入账前补全 staging Tag）。"""
    if not ledger_id:
        return None

    if is_bank_account_category(category_code) or account_code in {"1001", "1002"}:
        query = db.query(BankAccount).filter(BankAccount.ledger_id == ledger_id, BankAccount.is_active.is_(True))
        sub = (source_sub_code or "").strip()
        existing: BankAccount | None = None
        if sub:
            existing = query.filter(BankAccount.source_sub_code == sub).first()
        if existing is None and tag_value:
            existing = query.filter(BankAccount.account_name == tag_value).first()
        if existing and existing.account_name:
            return existing.account_name.strip()
        return None

    role = CATEGORY_COUNTERPARTY_ROLE.get(category_code)
    if role or category_code in CATEGORY_COUNTERPARTY_ROLE:
        name = (tag_value or "").strip()
        if not name:
            return None
        existing = db.query(Counterparty).filter(Counterparty.name == name, Counterparty.is_active.is_(True)).first()
        if existing:
            return existing.name.strip()
    return None


def enrich_tags_from_master(
    db: Session,
    ledger_id: int | None,
    tags: list[Any] | None,
    *,
    account_code: str | None = None,
) -> list[dict[str, Any]]:
    """确认入账前：用主数据规范全称覆盖 staging Tag（若主数据有更完整名称）。"""
    enriched: list[dict[str, Any]] = []
    for raw in tags or []:
        if not isinstance(raw, dict):
            continue
        tag = dict(raw)
        if tag.get("name_standardized"):
            enriched.append(tag)
            continue
        master_name = lookup_master_display_name(
            db,
            ledger_id,
            category_code=str(tag.get("category_code") or ""),
            tag_value=str(tag.get("tag_value") or ""),
            source_sub_code=tag.get("source_sub_code"),
            account_code=account_code,
        )
        if master_name:
            tag["display_name"] = master_name
            tag["name_standardized"] = True
        else:
            from app.services.doc_parsing.name_standardization_service import infer_name_standardized

            tag["name_standardized"] = infer_name_standardized(
                str(tag.get("display_name") or tag.get("tag_value") or ""),
                category_code=str(tag.get("category_code") or ""),
                tag_value=str(tag.get("tag_value") or ""),
                source_sub_code=tag.get("source_sub_code"),
                account_code=account_code,
            )
        enriched.append(tag)
    return enriched


def sync_dimension_value_to_master(
    db: Session,
    ledger_id: int | None,
    *,
    category_code: str,
    display_name: str,
    tag_value: str,
    source_sub_code: str | None = None,
    account_code: str | None = None,
) -> dict[str, Any]:
    """
    将规范全称写回主数据层。

    - account_detail / 银行：按 source_sub_code 更新或创建 bank_accounts
    - customer / supplier 等：按名称更新或创建 counterparties
    """
    if not ledger_id:
        return {"synced": False, "reason": "missing_ledger_id"}

    normalized_display = (display_name or "").strip()
    if not normalized_display:
        return {"synced": False, "reason": "empty_display_name"}

    if is_bank_account_category(category_code) or account_code in {"1001", "1002"}:
        return _sync_bank_account(
            db,
            ledger_id,
            display_name=normalized_display,
            tag_value=tag_value,
            source_sub_code=source_sub_code,
            account_code=account_code or "1002",
        )

    role = CATEGORY_COUNTERPARTY_ROLE.get(category_code)
    if role or category_code in CATEGORY_COUNTERPARTY_ROLE:
        return _sync_counterparty(
            db,
            display_name=normalized_display,
            tag_value=tag_value,
            role=role or "other",
        )

    return {"synced": False, "reason": "no_master_mapping", "category_code": category_code}


def _sync_bank_account(
    db: Session,
    ledger_id: int,
    *,
    display_name: str,
    tag_value: str,
    source_sub_code: str | None,
    account_code: str,
) -> dict[str, Any]:
    sub = (source_sub_code or "").strip()
    bank_name = (tag_value or display_name).strip() or display_name

    query = db.query(BankAccount).filter(BankAccount.ledger_id == ledger_id)
    existing: BankAccount | None = None
    if sub:
        existing = query.filter(BankAccount.source_sub_code == sub).first()
    if existing is None and tag_value:
        existing = query.filter(BankAccount.account_name == tag_value).first()

    if existing:
        existing.account_name = display_name
        if bank_name and existing.bank_name != bank_name:
            existing.bank_name = bank_name
        existing.coa_account_code = account_code or existing.coa_account_code or "1002"
        if sub and not existing.source_sub_code:
            existing.source_sub_code = sub
        db.commit()
        db.refresh(existing)
        return {"synced": True, "target": "bank_accounts", "action": "updated", "id": existing.id}

    account_no = f"SUB-{sub}" if sub else f"AUTO-{abs(hash(display_name)) % 10**8}"
    account = BankAccount(
        ledger_id=ledger_id,
        bank_name=bank_name,
        account_no=account_no,
        account_name=display_name,
        coa_account_code=account_code or "1002",
        source_sub_code=sub or None,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return {"synced": True, "target": "bank_accounts", "action": "created", "id": account.id}


def _sync_counterparty(
    db: Session,
    *,
    display_name: str,
    tag_value: str,
    role: str,
) -> dict[str, Any]:
    name = display_name
    shorthand = (tag_value or "").strip()
    existing = db.query(Counterparty).filter(Counterparty.name == name).first()
    if existing is None and shorthand and shorthand != name:
        existing = db.query(Counterparty).filter(Counterparty.name == shorthand).first()
        if existing:
            existing.name = name

    if existing:
        if role and existing.role != role:
            existing.role = role
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return {"synced": True, "target": "counterparties", "action": "updated", "id": existing.id}

    cp = Counterparty(name=name, role=role, is_active=True)
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return {"synced": True, "target": "counterparties", "action": "created", "id": cp.id}
