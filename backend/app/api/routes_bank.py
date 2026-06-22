from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import bank_service

router = APIRouter(prefix="/api/bank", tags=["bank"])


def require_ledger(ledger_id: int | None = Depends(get_current_ledger)) -> int:
    if ledger_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择账套")
    return ledger_id


class BankAccountResponse(BaseModel):
    id: int
    ledger_id: int
    bank_name: str
    account_no: str
    account_name: str
    coa_account_code: str
    opening_balance: float
    current_balance: float
    is_active: bool

    model_config = {"from_attributes": True}


class CreateBankAccountRequest(BaseModel):
    bank_name: str
    account_no: str
    account_name: str
    coa_account_code: str = "1002"
    opening_balance: float = 0


class CreateBankTransactionRequest(BaseModel):
    bank_account_id: int
    transaction_date: date
    direction: str
    amount: float = Field(gt=0)
    summary: str | None = None
    counterparty: str | None = None


class BankTransactionResponse(BaseModel):
    id: int
    bank_account_id: int
    ledger_id: int
    transaction_date: date
    direction: str
    amount: float
    summary: str | None
    counterparty: str | None
    reconciliation_status: str
    matched_entry_id: int | None

    model_config = {"from_attributes": True}


@router.get("/accounts", response_model=list[BankAccountResponse])
def list_bank_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> list[BankAccountResponse]:
    accounts = bank_service.list_accounts(db, ledger_id)
    return [BankAccountResponse.model_validate(account) for account in accounts]


@router.post("/accounts", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
def create_bank_account(
    payload: CreateBankAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> BankAccountResponse:
    account = bank_service.create_account(
        db,
        ledger_id=ledger_id,
        bank_name=payload.bank_name,
        account_no=payload.account_no,
        account_name=payload.account_name,
        coa_account_code=payload.coa_account_code,
        opening_balance=payload.opening_balance,
    )
    return BankAccountResponse.model_validate(account)


@router.get("/transactions", response_model=list[BankTransactionResponse])
def list_bank_transactions(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> list[BankTransactionResponse]:
    txns = bank_service.list_transactions(db, ledger_id, status=status_filter)
    return [BankTransactionResponse.model_validate(txn) for txn in txns]


@router.post("/transactions", response_model=BankTransactionResponse, status_code=status.HTTP_201_CREATED)
def create_bank_transaction(
    payload: CreateBankTransactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> BankTransactionResponse:
    try:
        if payload.direction not in {"in", "out"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="direction must be in or out")
        txn = bank_service.create_transaction(
            db,
            bank_account_id=payload.bank_account_id,
            ledger_id=ledger_id,
            transaction_date=payload.transaction_date,
            direction=payload.direction,
            amount=payload.amount,
            summary=payload.summary,
            counterparty=payload.counterparty,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BankTransactionResponse.model_validate(txn)


@router.get("/summary")
def bank_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> dict:
    return bank_service.get_summary(db, ledger_id)


@router.post("/reconcile/auto")
def auto_reconcile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> dict:
    return bank_service.auto_reconcile(db, ledger_id)
