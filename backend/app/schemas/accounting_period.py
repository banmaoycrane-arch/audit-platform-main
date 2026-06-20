from datetime import date, datetime

from pydantic import BaseModel


class AccountingPeriodCreate(BaseModel):
    organization_id: int
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
