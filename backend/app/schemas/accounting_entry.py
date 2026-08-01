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
    # 所属经济事件工单（一行分录通常关联 0 或 1 个事件；多关联时取 primary）。
    # event_id 用于跳转事件详情页，event_no 用于展示业务编号 E-xxx。
    event_id: int | None = None
    event_no: str | None = None

    model_config = {"from_attributes": True}


class TagUpdate(BaseModel):
    tags: list[str]
