from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class AccountingEntryRead(BaseModel):
    id: int
    organization_id: int
    ledger_id: int | None = None
    import_job_id: int | None = None
    voucher_no: str | None
    voucher_date: date | None
    summary: str | None
    account_code: str | None
    account_name: str | None
    debit_amount: Decimal
    credit_amount: Decimal
    counterparty: str | None
    normalized_text: str
    entry_line_no: int
    review_status: str = "draft"
    post_status: str = "draft"
    posted_at: datetime | None = None
    posted_by: int | None = None
    source_file_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TagUpdate(BaseModel):
    tags: list[str]
