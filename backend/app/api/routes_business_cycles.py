from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import BusinessCycle, CycleBreak, CycleStep
from app.db.session import get_db
from app.services.basic_data.business_cycle_service import BusinessCycleService

router = APIRouter(prefix="/api/business-cycles", tags=["business-cycles"])


# ==================== Pydantic Schemas ====================

class CycleCreate(BaseModel):
    organization_id: int
    cycle_type: str
    cycle_name: str
    start_date: Optional[date] = None


class CycleStatusUpdate(BaseModel):
    status: str


class StepCreate(BaseModel):
    step_order: int
    step_type: str
    step_name: str


class StepUpdate(BaseModel):
    status: Optional[str] = None
    actual_date: Optional[date] = None
    evidence_id: Optional[int] = None
    evidence_type: Optional[str] = None


class DetectBreaksRequest(BaseModel):
    cycle_id: int


# ==================== 序列化工具 ====================

def _cycle_to_dict(cycle: BusinessCycle) -> dict[str, Any]:
    return {
        "id": cycle.id,
        "organization_id": cycle.organization_id,
        "cycle_type": cycle.cycle_type,
        "cycle_name": cycle.cycle_name,
        "status": cycle.status,
        "start_date": cycle.start_date.isoformat() if cycle.start_date else None,
        "end_date": cycle.end_date.isoformat() if cycle.end_date else None,
        "completeness": cycle.completeness,
        "created_at": cycle.created_at.isoformat() if cycle.created_at else None,
    }


def _step_to_dict(step: CycleStep) -> dict[str, Any]:
    return {
        "id": step.id,
        "cycle_id": step.cycle_id,
        "step_order": step.step_order,
        "step_type": step.step_type,
        "step_name": step.step_name,
        "status": step.status,
        "actual_date": step.actual_date.isoformat() if step.actual_date else None,
        "evidence_id": step.evidence_id,
        "evidence_type": step.evidence_type,
    }


def _break_to_dict(b: CycleBreak) -> dict[str, Any]:
    return {
        "id": b.id,
        "cycle_id": b.cycle_id,
        "break_point": b.break_point,
        "break_type": b.break_type,
        "severity": b.severity,
        "description": b.description,
        "suggestion": b.suggestion,
        "audit_procedure": b.audit_procedure,
    }


# ==================== Routes ====================

@router.post("/")
def create_cycle(payload: CycleCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = BusinessCycleService(db)
    cycle = service.create_cycle(
        organization_id=payload.organization_id,
        cycle_type=payload.cycle_type,
        cycle_name=payload.cycle_name,
        start_date=payload.start_date,
    )
    return _cycle_to_dict(cycle)


@router.get("/")
def list_cycles(
    organization_id: int = Query(...),
    cycle_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    service = BusinessCycleService(db)
    cycles = service.get_cycles_by_organization(organization_id, cycle_type)
    return [_cycle_to_dict(c) for c in cycles]


@router.get("/{cycle_id}")
def get_cycle_detail(cycle_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = BusinessCycleService(db)
    cycle = service.get_cycle(cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="业务循环不存在")
    steps = (
        db.query(CycleStep)
        .filter(CycleStep.cycle_id == cycle_id)
        .order_by(CycleStep.step_order)
        .all()
    )
    breaks = db.query(CycleBreak).filter(CycleBreak.cycle_id == cycle_id).all()
    data = _cycle_to_dict(cycle)
    data["steps"] = [_step_to_dict(s) for s in steps]
    data["breaks"] = [_break_to_dict(b) for b in breaks]
    return data


@router.patch("/{cycle_id}/status")
def update_cycle_status(
    cycle_id: int, payload: CycleStatusUpdate, db: Session = Depends(get_db)
) -> dict[str, Any]:
    service = BusinessCycleService(db)
    cycle = service.update_cycle_status(cycle_id, payload.status)
    if not cycle:
        raise HTTPException(status_code=404, detail="业务循环不存在")
    return _cycle_to_dict(cycle)


@router.post("/{cycle_id}/steps")
def add_cycle_step(
    cycle_id: int, payload: StepCreate, db: Session = Depends(get_db)
) -> dict[str, Any]:
    service = BusinessCycleService(db)
    cycle = service.get_cycle(cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="业务循环不存在")
    step = service.add_step(
        cycle_id=cycle_id,
        step_order=payload.step_order,
        step_type=payload.step_type,
        step_name=payload.step_name,
    )
    return _step_to_dict(step)


@router.patch("/steps/{step_id}")
def update_cycle_step(
    step_id: int, payload: StepUpdate, db: Session = Depends(get_db)
) -> dict[str, Any]:
    service = BusinessCycleService(db)
    updates = payload.model_dump(exclude_unset=True)
    step = service.update_step(step_id, **updates)
    if not step:
        raise HTTPException(status_code=404, detail="步骤不存在")
    return _step_to_dict(step)


@router.post("/detect-breaks")
def detect_breaks(
    payload: DetectBreaksRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    service = BusinessCycleService(db)
    cycle = service.get_cycle(payload.cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="业务循环不存在")

    breaks = service.analyze_cycle_break(payload.cycle_id)
    persisted: list[dict[str, Any]] = []
    for b in breaks:
        cb = service.add_cycle_break(
            cycle_id=payload.cycle_id,
            break_point=b["step_order"],
            break_type=b["break_type"],
            severity=b["severity"],
            description=b["description"],
            suggestion=b["suggestion"],
            audit_procedure=b["audit_procedure"],
        )
        persisted.append(_break_to_dict(cb))

    return {"cycle_id": payload.cycle_id, "breaks": persisted}


@router.get("/{cycle_id}/risks")
def get_cycle_risks(cycle_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = BusinessCycleService(db)
    cycle = service.get_cycle(cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="业务循环不存在")
    return service.get_risk_extension(cycle_id)
