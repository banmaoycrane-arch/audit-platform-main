from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import audit_workflow_service

router = APIRouter(prefix="/api/audit/workflow", tags=["audit-workflow"])


def require_ledger(ledger_id: int | None = Depends(get_current_ledger)) -> int:
    if ledger_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择账套")
    return ledger_id


class WorkflowConfigResponse(BaseModel):
    project_id: int
    granularity: str
    enabled_procedures: list[str]
    auto_link_workpaper: bool
    created_at: str | None = None
    updated_at: str | None = None


class UpdateWorkflowConfigRequest(BaseModel):
    granularity: str | None = None
    enabled_procedures: list[str] | None = None
    auto_link_workpaper: bool | None = None


class ProcedureRunResponse(BaseModel):
    id: int
    project_id: int | None
    ledger_id: int
    procedure_key: str
    procedure_label: str
    status: str
    status_label: str
    title: str
    related_entity_type: str | None
    related_entity_id: int | None
    workpaper_index_id: int | None
    source_file_id: int | None
    recommended_by: str
    notes: str | None
    allowed_next_statuses: list[str]
    concluded_at: str | None
    created_at: str | None
    updated_at: str | None


class AdvanceProcedureRequest(BaseModel):
    action: str | None = None
    target_status: str | None = None
    notes: str | None = None


class CreateRunsFromRecommendationsRequest(BaseModel):
    recommendations: list[dict]
    project_id: int | None = None
    source_file_id: int | None = None


@router.get("/config", response_model=WorkflowConfigResponse)
def get_workflow_config(
    project_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowConfigResponse:
    row = audit_workflow_service.get_workflow_config(db, project_id)
    return WorkflowConfigResponse.model_validate(row)


@router.put("/config", response_model=WorkflowConfigResponse)
def update_workflow_config(
    project_id: int = Query(...),
    payload: UpdateWorkflowConfigRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowConfigResponse:
    row = audit_workflow_service.upsert_workflow_config(
        db,
        project_id,
        granularity=payload.granularity,
        enabled_procedures=payload.enabled_procedures,
        auto_link_workpaper=payload.auto_link_workpaper,
    )
    return WorkflowConfigResponse.model_validate(row)


@router.get("/runs", response_model=list[ProcedureRunResponse])
def list_procedure_runs(
    project_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> list[ProcedureRunResponse]:
    rows = audit_workflow_service.list_procedure_runs(
        db,
        ledger_id,
        project_id=project_id,
        status=status_filter,
    )
    return [ProcedureRunResponse.model_validate(row) for row in rows]


@router.get("/runs/{run_id}", response_model=ProcedureRunResponse)
def get_procedure_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> ProcedureRunResponse:
    row = audit_workflow_service.get_procedure_run(db, run_id, ledger_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="审计程序不存在")
    return ProcedureRunResponse.model_validate(row)


@router.post("/runs/{run_id}/advance", response_model=ProcedureRunResponse)
def advance_procedure_run(
    run_id: int,
    payload: AdvanceProcedureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> ProcedureRunResponse:
    try:
        row = audit_workflow_service.advance_procedure_run(
            db,
            run_id,
            ledger_id,
            action=payload.action,
            target_status=payload.target_status,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ProcedureRunResponse.model_validate(row)


@router.post("/runs/from-recommendations", response_model=list[ProcedureRunResponse])
def create_runs_from_recommendations(
    payload: CreateRunsFromRecommendationsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> list[ProcedureRunResponse]:
    rows = audit_workflow_service.create_runs_from_recommendations(
        db,
        ledger_id,
        payload.recommendations,
        project_id=payload.project_id,
        source_file_id=payload.source_file_id,
    )
    return [ProcedureRunResponse.model_validate(row) for row in rows]
