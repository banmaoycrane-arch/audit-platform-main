from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Organization
from app.db.session import get_db
from app.schemas.document_parsing import (
    BankStatementParseRequest,
    ContractParseRequest,
    InventoryDocumentParseRequest,
    InvoiceParseRequest,
    ParsedDocumentResponse,
)
from app.services.doc_parsing.document_parsing_service import DocumentParsingService

router = APIRouter(prefix="/api/parse", tags=["document-parsing"])


def _ensure_organization(db: Session, organization_id: int) -> None:
    if not db.get(Organization, organization_id):
        raise HTTPException(status_code=404, detail="组织不存在")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _response(document: Any, document_type: str, data: dict[str, Any]) -> ParsedDocumentResponse:
    return ParsedDocumentResponse(
        id=document.id,
        organization_id=document.organization_id,
        document_type=document_type,
        confidence_score=document.confidence_score,
        created_at=document.created_at,
        data=_json_safe(data),
    )


@router.post("/contract", response_model=ParsedDocumentResponse)
def parse_contract(payload: ContractParseRequest, db: Session = Depends(get_db)) -> ParsedDocumentResponse:
    _ensure_organization(db, payload.organization_id)
    service = DocumentParsingService(db)
    data = payload.model_dump(exclude={"organization_id"})
    contract = service.parse_contract(payload.organization_id, data)
    return _response(contract, "contract", data)


@router.post("/invoice", response_model=ParsedDocumentResponse)
def parse_invoice(payload: InvoiceParseRequest, db: Session = Depends(get_db)) -> ParsedDocumentResponse:
    _ensure_organization(db, payload.organization_id)
    service = DocumentParsingService(db)
    data = payload.model_dump(exclude={"organization_id"})
    invoice = service.parse_invoice(payload.organization_id, data)
    return _response(invoice, "invoice", data)


@router.post("/bank-statement", response_model=ParsedDocumentResponse)
def parse_bank_statement(payload: BankStatementParseRequest, db: Session = Depends(get_db)) -> ParsedDocumentResponse:
    _ensure_organization(db, payload.organization_id)
    service = DocumentParsingService(db)
    data = payload.model_dump(exclude={"organization_id"})
    statement = service.parse_bank_statement(payload.organization_id, data)
    return _response(statement, "bank_statement", data)


@router.post("/inventory-document", response_model=ParsedDocumentResponse)
def parse_inventory_document(payload: InventoryDocumentParseRequest, db: Session = Depends(get_db)) -> ParsedDocumentResponse:
    _ensure_organization(db, payload.organization_id)
    service = DocumentParsingService(db)
    data = payload.model_dump(exclude={"organization_id"})
    document = service.parse_inventory_document(payload.organization_id, data)
    return _response(document, "inventory_document", data)
