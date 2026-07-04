from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.accounting import three_way_match_service

router = APIRouter(prefix="/api/audit/purchase-match", tags=["purchase-match"])


def require_ledger(ledger_id: int | None = Depends(get_current_ledger)) -> int:
    if ledger_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择账簿")
    return ledger_id


class PurchaseMatchCheck(BaseModel):
    check_key: str
    label: str
    left_amount: float
    right_amount: float
    passed: bool


class PurchaseMatchException(BaseModel):
    exception_type: str
    exception_label: str
    message: str
    left_amount: float | None = None
    right_amount: float | None = None


class PurchaseMatchResult(BaseModel):
    ledger_id: int
    contract: dict[str, Any]
    invoices: list[dict[str, Any]]
    inventory_documents: list[dict[str, Any]]
    totals: dict[str, Any]
    checks: list[PurchaseMatchCheck]
    exceptions: list[PurchaseMatchException]
    match_status: str
    match_status_label: str


class PurchaseMatchSummary(BaseModel):
    ledger_id: int
    contract_count: int
    matched_count: int
    incomplete_count: int
    exception_count: int
    exception_items: list[dict[str, Any]]
    results: list[PurchaseMatchResult]


@router.get("", response_model=list[PurchaseMatchResult])
def list_purchase_matches(
    contract_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> list[PurchaseMatchResult]:
    try:
        rows = three_way_match_service.match_purchase_cycle(db, ledger_id, contract_id=contract_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return [PurchaseMatchResult.model_validate(row) for row in rows]


@router.get("/summary", response_model=PurchaseMatchSummary)
def purchase_match_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> PurchaseMatchSummary:
    row = three_way_match_service.summarize_purchase_matches(db, ledger_id)
    return PurchaseMatchSummary.model_validate(row)
