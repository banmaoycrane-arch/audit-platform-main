from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.models import AgentApproval
from app.db.session import get_db
from app.models.user import User
from app.services.agent_approval_service import (
    confirm_agent_tool_approval,
    request_agent_tool_approval,
    serialize_agent_approval,
)
from app.services.agent_controlled_execution_service import execute_confirmed_agent_draft
from app.services.agent_draft_review_service import (
    create_pending_draft_review,
    serialize_draft_review,
    submit_draft_review,
)
from app.services.agent_orchestration_service import build_due_diligence_orchestration_plan
from app.services.agent_service import plan_agent_task
from app.services.agent_tool_execution_service import run_low_risk_agent_tool
from app.services.agent_tool_registry import get_agent_tool
from app.services.audit_case_template_service import build_due_diligence_case_template
from app.services.execution_audit_service import create_execution_audit_log
from app.services.model_config_service import get_model_config_status

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AgentChatRequest(BaseModel):
    message: str


class AgentToolRunRequest(BaseModel):
    tool_name: str
    agent_role: str
    args: dict | None = None


class AgentApprovalConfirmRequest(BaseModel):
    comment: str | None = None


class AgentDraftReviewSubmitRequest(BaseModel):
    review_status: str
    review_comment: str
    returned_for_rework: bool = False
    allow_formal_delivery_design: bool = False


class DueDiligenceCaseTemplateRequest(BaseModel):
    scenario: str = "financial_due_diligence"


def _write_agent_audit_log(
    db: Session,
    current_user: User,
    ledger_id: int | None,
    message: str,
    tool_name: str,
    status: str,
    result: dict | None = None,
    error_message: str | None = None,
):
    task_plan = (result or {}).get("task_plan") or {}
    create_execution_audit_log(
        db=db,
        execution_source="agent_assisted",
        user=current_user,
        ledger_id=ledger_id,
        tool_name=tool_name,
        service_name="agent_service.plan_agent_task",
        status=status,
        risk_level=task_plan.get("risk_level", "low"),
        approval_required=task_plan.get("approval_required", False),
        agent_role=task_plan.get("agent_role", "navigation_agent"),
        input_summary={"message_length": len(message), "intent": (result or {}).get("intent")},
        error_message=error_message,
        business_object_type="agent_task_plan",
    )


def _write_agent_tool_audit_log(
    db: Session,
    current_user: User,
    ledger_id: int | None,
    payload: AgentToolRunRequest,
    status: str,
    error_message: str | None = None,
):
    tool = get_agent_tool(payload.tool_name) or {}
    create_execution_audit_log(
        db=db,
        execution_source="agent_auto",
        user=current_user,
        ledger_id=ledger_id,
        tool_name=payload.tool_name,
        service_name="agent_tool_execution_service.run_low_risk_agent_tool",
        status=status,
        risk_level=tool.get("risk_level", "low"),
        approval_required=tool.get("approval_required", False),
        agent_role=payload.agent_role,
        input_summary={"args_keys": sorted((payload.args or {}).keys())},
        error_message=error_message,
        business_object_type="agent_tool_call",
    )


def _write_agent_approval_audit_log(
    db: Session,
    current_user: User,
    ledger_id: int | None,
    tool_name: str,
    agent_role: str,
    status: str,
    approval_id: int | None = None,
    error_message: str | None = None,
):
    tool = get_agent_tool(tool_name) or {}
    create_execution_audit_log(
        db=db,
        execution_source="agent_assisted",
        user=current_user,
        ledger_id=ledger_id,
        tool_name=tool_name,
        service_name="agent_approval_service",
        status=status,
        risk_level=tool.get("risk_level", "medium"),
        approval_required=True,
        approval_id=approval_id,
        agent_role=agent_role,
        input_summary={"approval_id": approval_id},
        error_message=error_message,
        business_object_type="agent_approval",
        business_object_id=str(approval_id) if approval_id else None,
    )


def _write_agent_controlled_execution_audit_log(
    db: Session,
    current_user: User,
    ledger_id: int | None,
    approval_id: int,
    tool_name: str,
    agent_role: str,
    status: str,
    error_message: str | None = None,
):
    tool = get_agent_tool(tool_name) or {}
    create_execution_audit_log(
        db=db,
        execution_source="agent_assisted",
        user=current_user,
        ledger_id=ledger_id,
        tool_name=tool_name,
        service_name="agent_controlled_execution_service.execute_confirmed_agent_draft",
        status=status,
        risk_level=tool.get("risk_level", "medium"),
        approval_required=True,
        approval_id=approval_id,
        agent_role=agent_role,
        input_summary={"approval_id": approval_id, "output_type": "draft"},
        error_message=error_message,
        business_object_type="agent_controlled_draft_execution",
        business_object_id=str(approval_id),
    )



def _write_agent_draft_review_audit_log(
    db: Session,
    current_user: User,
    ledger_id: int | None,
    review: dict | None,
    status: str,
    action: str,
    error_message: str | None = None,
):
    create_execution_audit_log(
        db=db,
        execution_source="agent_assisted",
        user=current_user,
        ledger_id=ledger_id,
        tool_name=(review or {}).get("tool_name", "agent_draft_review"),
        service_name="agent_draft_review_service",
        status=status,
        risk_level="medium",
        approval_required=True,
        approval_id=(review or {}).get("approval_id"),
        agent_role=(review or {}).get("agent_role"),
        input_summary={
            "action": action,
            "review_id": (review or {}).get("id"),
            "review_status": (review or {}).get("review_status"),
            "returned_for_rework": (review or {}).get("returned_for_rework"),
            "allow_formal_delivery_design": (review or {}).get("allow_formal_delivery_design"),
        },
        error_message=error_message,
        business_object_type="agent_draft_review",
        business_object_id=str((review or {}).get("id")) if (review or {}).get("id") else None,
    )



def _write_agent_orchestration_audit_log(
    db: Session,
    current_user: User,
    ledger_id: int | None,
    message: str,
    status: str,
    plan: dict | None = None,
    error_message: str | None = None,
):
    create_execution_audit_log(
        db=db,
        execution_source="agent_assisted",
        user=current_user,
        ledger_id=ledger_id,
        tool_name="agent_orchestration_plan",
        service_name="agent_orchestration_service.build_due_diligence_orchestration_plan",
        status=status,
        risk_level="high",
        approval_required=True,
        agent_role="orchestrator_agent",
        input_summary={
            "message_length": len(message),
            "intent": (plan or {}).get("intent"),
            "step_count": len((plan or {}).get("coordination_steps", [])),
        },
        error_message=error_message,
        business_object_type="agent_orchestration_plan",
    )


@router.get("/model/config")
def get_agent_model_config(
    current_user: User = Depends(get_current_user),
) -> dict:
    return get_model_config_status()


@router.post("/chat")
def agent_chat(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict:
    message = payload.message.strip()
    if not message:
        _write_agent_audit_log(
            db, current_user, ledger_id, message, "agent_chat", "failed", error_message="message 不能为空"
        )
        raise HTTPException(status_code=400, detail="message 不能为空")

    result = plan_agent_task(message, current_user.id, ledger_id)
    _write_agent_audit_log(db, current_user, ledger_id, message, "agent_chat", "success", result=result)
    return result


@router.post("/tasks/plan")
def agent_task_plan(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict:
    message = payload.message.strip()
    if not message:
        _write_agent_audit_log(
            db, current_user, ledger_id, message, "agent_tasks_plan", "failed", error_message="message 不能为空"
        )
        raise HTTPException(status_code=400, detail="message 不能为空")

    result = plan_agent_task(message, current_user.id, ledger_id)
    _write_agent_audit_log(db, current_user, ledger_id, message, "agent_tasks_plan", "success", result=result)
    return result


@router.post("/case-templates/due-diligence")
def get_due_diligence_case_template(
    payload: DueDiligenceCaseTemplateRequest,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict:
    template = build_due_diligence_case_template(payload.scenario)
    create_execution_audit_log(
        db=db,
        execution_source="agent_assisted",
        user=current_user,
        ledger_id=ledger_id,
        tool_name="due_diligence_case_template",
        service_name="audit_case_template_service.build_due_diligence_case_template",
        status="success",
        risk_level="medium",
        approval_required=True,
        agent_role="orchestrator_agent",
        input_summary={"scenario": template["scenario"]},
        business_object_type="agent_case_template",
    )
    return template


@router.post("/orchestration/plan")
def plan_agent_orchestration(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict:
    message = payload.message.strip()
    if not message:
        _write_agent_orchestration_audit_log(
            db, current_user, ledger_id, message, "failed", error_message="message 不能为空"
        )
        raise HTTPException(status_code=400, detail="message 不能为空")

    plan = build_due_diligence_orchestration_plan(message, current_user.id, ledger_id)
    _write_agent_orchestration_audit_log(db, current_user, ledger_id, message, "success", plan=plan)
    return plan


@router.post("/tools/run")
def run_agent_tool(
    payload: AgentToolRunRequest,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = run_low_risk_agent_tool(
            db=db,
            tool_name=payload.tool_name,
            agent_role=payload.agent_role,
            args=payload.args,
        )
    except PermissionError as exc:
        _write_agent_tool_audit_log(db, current_user, ledger_id, payload, "failed", str(exc))
        raise HTTPException(status_code=403, detail=str(exc))
    except NotImplementedError as exc:
        _write_agent_tool_audit_log(db, current_user, ledger_id, payload, "failed", str(exc))
        raise HTTPException(status_code=501, detail=str(exc))

    _write_agent_tool_audit_log(db, current_user, ledger_id, payload, "success")
    return result


@router.post("/approvals/request")
def request_agent_approval(
    payload: AgentToolRunRequest,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict:
    try:
        approval = request_agent_tool_approval(
            db=db,
            tool_name=payload.tool_name,
            agent_role=payload.agent_role,
            args=payload.args,
            current_user=current_user,
            ledger_id=ledger_id,
        )
    except PermissionError as exc:
        _write_agent_approval_audit_log(
            db, current_user, ledger_id, payload.tool_name, payload.agent_role, "failed", error_message=str(exc)
        )
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        _write_agent_approval_audit_log(
            db, current_user, ledger_id, payload.tool_name, payload.agent_role, "failed", error_message=str(exc)
        )
        raise HTTPException(status_code=400, detail=str(exc))

    _write_agent_approval_audit_log(
        db, current_user, ledger_id, payload.tool_name, payload.agent_role, "success", approval_id=approval.id
    )
    return serialize_agent_approval(approval)


@router.post("/approvals/{approval_id}/confirm")
def confirm_agent_approval(
    approval_id: int,
    payload: AgentApprovalConfirmRequest,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict:
    try:
        approval = confirm_agent_tool_approval(db, approval_id, current_user, payload.comment)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _write_agent_approval_audit_log(
        db,
        current_user,
        ledger_id,
        approval.tool_name,
        approval.agent_role,
        "success",
        approval_id=approval.id,
    )
    return serialize_agent_approval(approval)


@router.post("/approvals/{approval_id}/execute-draft")
def execute_agent_approval_draft(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict:
    approval = db.get(AgentApproval, approval_id)
    tool_name = approval.tool_name if approval else "unknown_agent_tool"
    agent_role = approval.agent_role if approval else "unknown_agent_role"
    try:
        result = execute_confirmed_agent_draft(db, approval_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        _write_agent_controlled_execution_audit_log(
            db, current_user, ledger_id, approval_id, tool_name, agent_role, "failed", str(exc)
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        _write_agent_controlled_execution_audit_log(
            db, current_user, ledger_id, approval_id, tool_name, agent_role, "failed", str(exc)
        )
        raise HTTPException(status_code=403, detail=str(exc))

    _write_agent_controlled_execution_audit_log(
        db,
        current_user,
        ledger_id,
        approval_id,
        result["tool_name"],
        result["agent_role"],
        "success",
    )
    return result


@router.post("/approvals/{approval_id}/draft-review")
def create_agent_draft_review(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict:
    try:
        review = create_pending_draft_review(db, approval_id, current_user, ledger_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        _write_agent_draft_review_audit_log(
            db, current_user, ledger_id, {"approval_id": approval_id}, "failed", "create", str(exc)
        )
        raise HTTPException(status_code=400, detail=str(exc))

    data = serialize_draft_review(review)
    _write_agent_draft_review_audit_log(db, current_user, ledger_id, data, "success", "create")
    return data


@router.post("/draft-reviews/{review_id}/submit")
def submit_agent_draft_review(
    review_id: int,
    payload: AgentDraftReviewSubmitRequest,
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict:
    try:
        review = submit_draft_review(
            db=db,
            review_id=review_id,
            current_user=current_user,
            review_status=payload.review_status,
            review_comment=payload.review_comment,
            returned_for_rework=payload.returned_for_rework,
            allow_formal_delivery_design=payload.allow_formal_delivery_design,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        _write_agent_draft_review_audit_log(
            db, current_user, ledger_id, {"id": review_id}, "failed", "submit", str(exc)
        )
        raise HTTPException(status_code=400, detail=str(exc))

    data = serialize_draft_review(review)
    _write_agent_draft_review_audit_log(db, current_user, ledger_id, data, "success", "submit")
    return data
