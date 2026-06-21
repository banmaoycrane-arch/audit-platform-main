from datetime import date, datetime
from pydantic import BaseModel


class AccountingEntryRead(BaseModel):
    id: int
    organization_id: int
    import_job_id: int
    voucher_no: str | None
    voucher_date: date | None
    summary: str | None
    account_code: str | None
    account_name: str | None
    debit_amount: float
    credit_amount: float
    counterparty: str | None
    normalized_text: str
    entry_line_no: int
    review_status: str = "draft"
    created_at: datetime

    model_config = {"from_attributes": True}


class TagUpdate(BaseModel):
    tags: list[str]
