from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class DocumentParseRequest(BaseModel):
    organization_id: int
    data: dict[str, Any]


class ParsedDocumentResponse(BaseModel):
    id: int
    organization_id: int
    document_type: str
    confidence_score: float
    created_at: datetime
    data: dict[str, Any]

    model_config = {"from_attributes": True}


class ContractParseRequest(BaseModel):
    organization_id: int
    contract_no: str | None = None
    contract_type: str = "service"
    contract_name: str | None = None
    sign_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    effective_date: date | None = None
    contract_amount: float | None = None
    currency: str = "CNY"
    tax_rate: float | None = None
    tax_amount: float | None = None
    extracted_text: str | None = None
    confidence_score: float = 0.8
    parties: list[dict[str, Any]] = []
    performance_obligations_list: list[dict[str, Any]] = []
    payment_terms: list[dict[str, Any]] = []


class InvoiceParseRequest(BaseModel):
    organization_id: int
    invoice_no: str | None = None
    invoice_code: str | None = None
    invoice_type: str = "增值税专用发票"
    invoice_status: str = "normal"
    invoice_date: date | None = None
    buyer_name: str | None = None
    buyer_tax_no: str | None = None
    seller_name: str | None = None
    seller_tax_no: str | None = None
    amount_excluding_tax: float | None = None
    tax_rate: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    extracted_text: str | None = None
    confidence_score: float = 0.8
    items: list[dict[str, Any]] = []


class BankStatementParseRequest(BaseModel):
    organization_id: int
    transaction_no: str | None = None
    transaction_date: date | None = None
    transaction_time: str | None = None
    transaction_type: str = "income"
    account_name: str | None = None
    account_no: str | None = None
    bank_name: str | None = None
    counterparty_name: str | None = None
    counterparty_account: str | None = None
    counterparty_bank: str | None = None
    amount: float | None = None
    balance: float | None = None
    summary: str | None = None
    purpose: str | None = None
    remark: str | None = None
    extracted_text: str | None = None
    confidence_score: float = 0.8


class InventoryDocumentParseRequest(BaseModel):
    organization_id: int
    document_no: str
    document_type: str = "inventory_in"
    document_date: date | None = None
    warehouse_name: str | None = None
    warehouse_code: str | None = None
    counterparty_type: str | None = None
    counterparty_name: str | None = None
    counterparty_code: str | None = None
    total_quantity: float | None = None
    total_amount: float | None = None
    inspector: str | None = None
    inspect_date: date | None = None
    inspect_result: str | None = None
    extracted_text: str | None = None
    confidence_score: float = 0.8
    items: list[dict[str, Any]] = []
