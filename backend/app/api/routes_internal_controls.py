from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import ControlAlert, ControlTest, InternalControl
from app.db.session import get_db
from app.services.internal_control_service import InternalControlService

router = APIRouter(prefix="/api/internal-controls", tags=["internal-controls"])


class ControlTestPayload(BaseModel):
    organization_id: int
    control_id: int
    transaction_id: Optional[int] = None
    evidence_found: Optional[List[str]] = None
    evidence_missing: Optional[List[str]] = None


def _control_to_dict(control: InternalControl) -> dict[str, Any]:
    return {
        "id": control.id,
        "control_code": control.control_code,
        "control_name": control.control_name,
        "control_type": control.control_type,
        "control_category": control.control_category,
        "description": control.description,
        "objective": control.objective,
        "trigger_conditions": list(control.trigger_conditions or []),
        "evidence_required": list(control.evidence_required or []),
        "frequency": control.frequency,
        "industries": list(control.industries or []),
        "company_size": control.company_size,
        "risk_category": control.risk_category,
        "inherent_risk": control.inherent_risk,
        "control_risk": control.control_risk,
        "created_at": control.created_at.isoformat() if control.created_at else None,
    }


def _test_to_dict(test: ControlTest) -> dict[str, Any]:
    return {
        "id": test.id,
        "organization_id": test.organization_id,
        "control_id": test.control_id,
        "transaction_id": test.transaction_id,
        "is_executed": test.is_executed,
        "evidence_found": list(test.evidence_found or []),
        "evidence_missing": list(test.evidence_missing or []),
        "execution_quality": test.execution_quality,
        "inherent_risk": test.inherent_risk,
        "control_risk": test.control_risk,
        "detection_risk": test.detection_risk,
        "overall_risk": test.overall_risk,
        "alert_level": test.alert_level,
        "alert_message": test.alert_message,
        "suggested_procedure": test.suggested_procedure,
        "tested_at": test.tested_at.isoformat() if test.tested_at else None,
    }


def _alert_to_dict(alert: ControlAlert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "organization_id": alert.organization_id,
        "control_id": alert.control_id,
        "test_id": alert.test_id,
        "alert_level": alert.alert_level,
        "business_type": alert.business_type,
        "affected_transaction": alert.affected_transaction,
        "evidence_involved": list(alert.evidence_involved or []),
        "problem_type": alert.problem_type,
        "description": alert.description,
        "inherent_risk": alert.inherent_risk,
        "control_risk": alert.control_risk,
        "detection_risk": alert.detection_risk,
        "overall_risk": alert.overall_risk,
        "suggested_procedure": alert.suggested_procedure,
        "priority": alert.priority,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


@router.post("/initialize")
def initialize_default_controls(db: Session = Depends(get_db)) -> dict[str, Any]:
    service = InternalControlService(db)
    service.initialize_default_controls()
    count = db.query(InternalControl).count()
    return {"count": count, "message": "默认内控程序已初始化"}


@router.get("/")
def list_controls(
    category: Optional[str] = Query(default=None),
    industry: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    service = InternalControlService(db)
    if industry:
        controls = service.get_controls_by_industry(industry)
    elif category:
        controls = service.get_controls_by_category(category)
    else:
        controls = service.get_controls_by_category(None)
    return [_control_to_dict(c) for c in controls]


@router.get("/alerts")
def list_alerts(
    organization_id: int = Query(...),
    alert_level: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    service = InternalControlService(db)
    alerts = service.get_alerts_by_organization(organization_id, alert_level)
    return [_alert_to_dict(a) for a in alerts]


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = InternalControlService(db)
    ok = service.acknowledge_alert(alert_id)
    return {"ok": ok}


@router.get("/risk-matrix")
def get_risk_matrix(
    organization_id: int = Query(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = InternalControlService(db)
    return service.calculate_risk_matrix(organization_id)


@router.post("/test")
def execute_control_test(
    payload: ControlTestPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = InternalControlService(db)
    try:
        test = service.execute_control_test(
            organization_id=payload.organization_id,
            control_id=payload.control_id,
            transaction_id=payload.transaction_id,
            evidence_found=payload.evidence_found,
            evidence_missing=payload.evidence_missing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _test_to_dict(test)


@router.get("/{control_id}")
def get_control(control_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = InternalControlService(db)
    control = service.get_control(control_id)
    if not control:
        raise HTTPException(status_code=404, detail=f"内控程序 {control_id} 不存在")
    return _control_to_dict(control)
