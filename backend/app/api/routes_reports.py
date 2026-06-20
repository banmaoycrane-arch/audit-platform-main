from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod
from app.db.session import get_db
from app.services import financial_statements_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _check_period(db: Session, period_id: int) -> None:
    if not db.get(AccountingPeriod, period_id):
        raise HTTPException(status_code=404, detail="会计期间不存在")


@router.get("/trial-balance")
def trial_balance(organization_id: int, period_id: int, db: Session = Depends(get_db)) -> dict:
    _check_period(db, period_id)
    return financial_statements_service.trial_balance_report(db, organization_id, period_id)


@router.get("/balance-sheet")
def balance_sheet(organization_id: int, period_id: int, db: Session = Depends(get_db)) -> dict:
    _check_period(db, period_id)
    return financial_statements_service.balance_sheet(db, organization_id, period_id)


@router.get("/income-statement")
def income_statement(organization_id: int, period_id: int, db: Session = Depends(get_db)) -> dict:
    _check_period(db, period_id)
    return financial_statements_service.income_statement(db, organization_id, period_id)
