"""账簿上下文解析：统一 organization 与 ledger 的绑定关系。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod, ImportJob, Organization
from app.models.ledger import Ledger


def resolve_organization_id_for_ledger(db: Session, ledger_id: int) -> int | None:
    """查找账簿已绑定的 organization_id，不存在则返回 None。"""
    job = (
        db.query(ImportJob)
        .filter(ImportJob.ledger_id == ledger_id)
        .order_by(ImportJob.id.desc())
        .first()
    )
    if job:
        return job.organization_id

    period = (
        db.query(AccountingPeriod)
        .filter(AccountingPeriod.ledger_id == ledger_id)
        .order_by(AccountingPeriod.id.desc())
        .first()
    )
    if period:
        return period.organization_id

    entry = (
        db.query(AccountingEntry)
        .filter(AccountingEntry.ledger_id == ledger_id)
        .order_by(AccountingEntry.id.desc())
        .first()
    )
    if entry:
        return entry.organization_id

    return None


def resolve_or_create_organization_for_ledger(
    db: Session,
    ledger_id: int,
    organization_name: str | None = None,
    industry: str | None = None,
    fiscal_year: int | None = None,
) -> int:
    """为账簿解析或创建唯一 organization，避免每次导入都新建临时组织。"""
    existing_id = resolve_organization_id_for_ledger(db, ledger_id)
    if existing_id is not None:
        return existing_id

    ledger = db.get(Ledger, ledger_id)
    org_name = organization_name or (ledger.name if ledger else "默认企业")
    organization = Organization(name=org_name, industry=industry, fiscal_year=fiscal_year)
    db.add(organization)
    db.flush()
    return organization.id
