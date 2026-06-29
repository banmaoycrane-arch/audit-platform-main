"""账簿会计期间时间线初始化。

每个账簿在创建时对齐会计起始时间线（默认创建当日），并种子化首个开放会计期间。
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod, Organization
from app.models.ledger import Ledger


def month_period_bounds(anchor: date) -> tuple[str, date, date]:
    """按自然月生成期间编码与起止日期。"""
    period_code = f"{anchor.year:04d}-{anchor.month:02d}"
    start = date(anchor.year, anchor.month, 1)
    last_day = monthrange(anchor.year, anchor.month)[1]
    end = date(anchor.year, anchor.month, last_day)
    return period_code, start, end


def initialize_ledger_timeline(
    db: Session,
    ledger: Ledger,
    *,
    organization_name: str | None = None,
) -> tuple[Organization, AccountingPeriod]:
    """为新建账簿创建组织容器与首个会计期间。"""
    anchor = ledger.accounting_start_date or date.today()
    organization = Organization(
        name=organization_name or ledger.name,
        fiscal_year=anchor.year,
    )
    db.add(organization)
    db.flush()

    period_code, start_date, end_date = month_period_bounds(anchor)
    period = AccountingPeriod(
        organization_id=organization.id,
        ledger_id=ledger.id,
        period_code=period_code,
        period_type="monthly",
        start_date=start_date,
        end_date=end_date,
        status="open",
    )
    db.add(period)
    db.flush()
    return organization, period
