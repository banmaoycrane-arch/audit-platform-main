from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.session import get_db
from app.models.user import User
import app.services.audit.confirmation_service as confirmation_service

router = APIRouter(prefix="/api/confirmations", tags=["confirmations"])


def require_ledger(ledger_id: int | None = Depends(get_current_ledger)) -> int:
    if ledger_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择账簿")
    return ledger_id


class ConfirmationResponse(BaseModel):
    id: int
    ledger_id: int
    counterparty_id: int | None
    counterparty_name: str | None
    balance_type: str
    balance_type_label: str
    book_balance: float
    confirmation_amount: float
    reply_amount: float | None
    difference: float | None
    status: str
    sent_at: str | None
    replied_at: str | None
    source_file_id: int | None
    created_at: str | None


class GenerateConfirmationsRequest(BaseModel):
    counterparty_ids: list[int] | None = None
    balance_types: list[str] | None = None


class UpdateConfirmationRequest(BaseModel):
    status: str | None = None
    confirmation_amount: float | None = Field(default=None, ge=0)
    reply_amount: float | None = Field(default=None, ge=0)
    source_file_id: int | None = None


class RecordReplyRequest(BaseModel):
    reply_amount: float = Field(gt=0)
    source_file_id: int | None = None


@router.get("", response_model=list[ConfirmationResponse])
def list_confirmations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> list[ConfirmationResponse]:
    rows = confirmation_service.list_confirmations(db, ledger_id)
    return [ConfirmationResponse.model_validate(row) for row in rows]


@router.post("/generate", response_model=list[ConfirmationResponse], status_code=status.HTTP_201_CREATED)
def generate_confirmations(
    payload: GenerateConfirmationsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> list[ConfirmationResponse]:
    rows = confirmation_service.create_from_balances(
        db,
        ledger_id,
        counterparty_ids=payload.counterparty_ids,
        balance_types=payload.balance_types,
    )
    return [ConfirmationResponse.model_validate(row) for row in rows]


@router.get("/{confirmation_id}", response_model=ConfirmationResponse)
def get_confirmation(
    confirmation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> ConfirmationResponse:
    row = confirmation_service.get_confirmation(db, confirmation_id, ledger_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="函证记录不存在")
    return ConfirmationResponse.model_validate(row)


@router.patch("/{confirmation_id}", response_model=ConfirmationResponse)
def update_confirmation(
    confirmation_id: int,
    payload: UpdateConfirmationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> ConfirmationResponse:
    try:
        row = confirmation_service.update_confirmation(
            db,
            confirmation_id,
            ledger_id,
            status=payload.status,
            confirmation_amount=payload.confirmation_amount,
            reply_amount=payload.reply_amount,
            source_file_id=payload.source_file_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ConfirmationResponse.model_validate(row)


@router.post("/{confirmation_id}/reply", response_model=ConfirmationResponse)
def record_confirmation_reply(
    confirmation_id: int,
    payload: RecordReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> ConfirmationResponse:
    try:
        row = confirmation_service.record_reply(
            db,
            confirmation_id,
            ledger_id,
            payload.reply_amount,
            source_file_id=payload.source_file_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ConfirmationResponse.model_validate(row)
