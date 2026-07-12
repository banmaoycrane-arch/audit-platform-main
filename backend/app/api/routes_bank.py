from typing import Any, Literal
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.basic_data import bank_service
from app.services.basic_data import bank_reconciliation_service

router = APIRouter(prefix="/api/bank", tags=["bank"])


def require_ledger(ledger_id: int | None = Depends(get_current_ledger)) -> int:
    if ledger_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择账簿")
    return ledger_id


class BankAccountResponse(BaseModel):
    id: int
    ledger_id: int
    bank_name: str
    account_no: str
    account_name: str
    coa_account_code: str
    source_sub_code: str | None = None
    opening_balance: float
    current_balance: float
    is_active: bool

    model_config = {"from_attributes": True}


class CreateBankAccountRequest(BaseModel):
    bank_name: str
    account_no: str
    account_name: str
    coa_account_code: str = "1002"
    source_sub_code: str | None = None
    opening_balance: float = 0


class UpdateBankAccountRequest(BaseModel):
    bank_name: str
    account_no: str
    account_name: str
    coa_account_code: str = "1002"
    source_sub_code: str | None = None


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
        source_sub_code=payload.source_sub_code,
        opening_balance=payload.opening_balance,
    )
    return BankAccountResponse.model_validate(account)


@router.put("/accounts/{account_id}", response_model=BankAccountResponse)
def update_bank_account(
    account_id: int,
    payload: UpdateBankAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> BankAccountResponse:
    try:
        account = bank_service.update_account(
            db,
            account_id=account_id,
            ledger_id=ledger_id,
            bank_name=payload.bank_name,
            account_no=payload.account_no,
            account_name=payload.account_name,
            coa_account_code=payload.coa_account_code,
            source_sub_code=payload.source_sub_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BankAccountResponse.model_validate(account)


@router.delete("/accounts/{account_id}")
def delete_bank_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> dict[str, str]:
    try:
        bank_service.deactivate_account(db, account_id=account_id, ledger_id=ledger_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "deleted"}


class BulkBankAccountImportRequest(BaseModel):
    records: list[dict[str, Any]]


@router.post("/accounts/bulk-import")
def bulk_import_bank_accounts(
    payload: BulkBankAccountImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> dict[str, Any]:
    return bank_service.bulk_import_accounts(db, ledger_id=ledger_id, records=payload.records)


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
) -> dict[str, Any]:
    return bank_service.get_summary(db, ledger_id)


@router.post("/reconcile/auto")
def auto_reconcile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> dict[str, Any]:
    return bank_service.auto_reconcile(db, ledger_id)


class CreateBankReconciliationRequest(BaseModel):
    bank_account_id: int
    period_end: date
    statement_balance: float | None = None


class BankReconciliationItemResponse(BaseModel):
    id: int
    item_type: str
    item_type_label: str
    amount: float
    direction: str | None
    bank_transaction_id: int | None
    entry_id: int | None
    summary: str | None
    note: str | None


class BankReconciliationResponse(BaseModel):
    id: int
    ledger_id: int
    bank_account_id: int
    bank_name: str | None
    account_no: str | None
    period_end: str
    statement_balance: float
    book_balance: float
    adjusted_statement_balance: float
    adjusted_book_balance: float
    difference: float
    status: str
    created_at: str | None
    items: list[BankReconciliationItemResponse]


@router.get("/reconciliations", response_model=list[BankReconciliationResponse])
def list_bank_reconciliations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> list[BankReconciliationResponse]:
    rows = bank_reconciliation_service.list_reconciliations(db, ledger_id)
    return [BankReconciliationResponse.model_validate(row) for row in rows]


@router.post("/reconciliations", response_model=BankReconciliationResponse, status_code=status.HTTP_201_CREATED)
def create_bank_reconciliation_draft(
    payload: CreateBankReconciliationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> BankReconciliationResponse:
    try:
        row = bank_reconciliation_service.build_draft(
            db,
            ledger_id,
            payload.bank_account_id,
            payload.period_end,
            statement_balance=payload.statement_balance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BankReconciliationResponse.model_validate(row)


@router.get("/reconciliations/{reconciliation_id}", response_model=BankReconciliationResponse)
def get_bank_reconciliation(
    reconciliation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> BankReconciliationResponse:
    row = bank_reconciliation_service.get_reconciliation(db, reconciliation_id, ledger_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="调节表不存在")
    return BankReconciliationResponse.model_validate(row)
