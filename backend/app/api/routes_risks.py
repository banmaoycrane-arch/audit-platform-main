from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import AuditRisk, ReviewAction, RiskEvidence
from app.db.session import get_db
from app.schemas.risk import AuditRiskRead, RiskDetailRead, RiskReviewUpdate

router = APIRouter(prefix="/api/risks", tags=["risks"])


@router.get("", response_model=list[AuditRiskRead])
def list_risks(import_job_id: int | None = None, db: Session = Depends(get_db)) -> list[AuditRisk]:
    query = db.query(AuditRisk).order_by(AuditRisk.id.desc())
    if import_job_id:
        query = query.filter(AuditRisk.import_job_id == import_job_id)
    return query.limit(200).all()


@router.get("/{risk_id}", response_model=RiskDetailRead)
def get_risk(risk_id: int, db: Session = Depends(get_db)) -> dict:
    risk = db.get(AuditRisk, risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="风险不存在")
    evidence = db.query(RiskEvidence).filter(RiskEvidence.risk_id == risk_id).all()
    return {**risk.__dict__, "evidence": evidence}


@router.patch("/{risk_id}/review", response_model=AuditRiskRead)
def review_risk(risk_id: int, payload: RiskReviewUpdate, db: Session = Depends(get_db)) -> AuditRisk:
    risk = db.get(AuditRisk, risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="风险不存在")
    risk.status = payload.action
    db.add(ReviewAction(risk_id=risk.id, action=payload.action, comment=payload.comment))
    db.commit()
    db.refresh(risk)
    return risk
