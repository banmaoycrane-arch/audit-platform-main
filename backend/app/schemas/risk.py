from datetime import datetime
from pydantic import BaseModel


class RiskEvidenceRead(BaseModel):
    id: int
    risk_id: int
    evidence_type: str
    source_id: int
    source_text: str
    similarity_score: float | None
    reason: str

    model_config = {"from_attributes": True}


class AuditRiskRead(BaseModel):
    id: int
    organization_id: int
    import_job_id: int
    risk_type: str
    risk_level: str
    title: str
    description: str
    status: str
    confidence: float
    created_at: datetime

    model_config = {"from_attributes": True}


class RiskDetailRead(AuditRiskRead):
    evidence: list[RiskEvidenceRead]


class RiskReviewUpdate(BaseModel):
    action: str
    comment: str | None = None
