from datetime import date, datetime

from pydantic import BaseModel


class AccountingPeriodCreate(BaseModel):
    organization_id: int | None = None
    ledger_id: int | None = None
    period_code: str
    start_date: date
    end_date: date
    period_type: str = "monthly"


class AccountingPeriodSuggestion(BaseModel):
    period_code: str
    period_type: str
    start_date: date
    end_date: date


class AccountingPeriodRecommendation(BaseModel):
    matched_period: "AccountingPeriodRead | None" = None
    suggested_period: AccountingPeriodSuggestion | None = None
    reason: str


class AccountingPeriodRead(BaseModel):
    id: int
    organization_id: int
    period_code: str
    period_type: str
    start_date: date
    end_date: date
    status: str
    snapshot_status: str | None = None
    snapshot_version: int = 0
    source: str = "live_calculation"
    closed_at: datetime | None = None
    reopened_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PeriodActionRequest(BaseModel):
    operator: str = "system"
    reason: str | None = None


class SnapshotCreateRequest(BaseModel):
    dimensions: list[str] | None = None


class PeriodSnapshotRead(BaseModel):
    id: int
    period_id: int
    snapshot_version: int
    dimension_type: str
    dimension_id: int | None
    dimension_code: str | None
    dimension_name: str | None
    amount: float
    quantity: float | None
    currency: str
    snapshot_status: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class PeriodSnapshotResponse(BaseModel):
    period: AccountingPeriodRead
    snapshots: list[PeriodSnapshotRead]


class PeriodBatchCreateRequest(BaseModel):
    organization_id: int | None = None
    ledger_id: int | None = None
    start_date: date
    end_date: date
    period_type: str = "monthly"


class PeriodBatchCreateResponse(BaseModel):
    created_count: int
    skipped_count: int
    created_periods: list[AccountingPeriodRead]
    skipped_period_codes: list[str]


class PlTransferBatchRequest(BaseModel):
    ledger_id: int
    period_ids: list[int] | None = None
    from_period_id: int | None = None
    to_period_id: int | None = None
    stop_on_error: bool = True
    skip_transferred: bool = True


class PlTransferBatchItemResult(BaseModel):
    period_id: int
    period_code: str
    status: str
    voucher_no: str | None = None
    lines: int | None = None
    net_profit: float | None = None
    error: str | None = None
    reason: str | None = None


class PlTransferBatchResponse(BaseModel):
    ledger_id: int
    total: int
    succeeded_count: int
    failed_count: int
    skipped_count: int
    stopped_early: bool
    succeeded: list[PlTransferBatchItemResult]
    failed: list[PlTransferBatchItemResult]
    skipped: list[PlTransferBatchItemResult]
