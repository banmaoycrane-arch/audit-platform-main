from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.binding_request import BindingRequest
from app.models.ledger import Ledger
from app.models.project import Project
from app.models.team import Team
from app.models.user import User
from app.services import platform_permission_service
from app.api.routes_binding_requests import attach_display_names, build_binding_request_response, BindingRequestResponse

router = APIRouter(prefix="/api/super-admin", tags=["super-admin"])


class SuperAdminOverviewResponse(BaseModel):
    user_count: int
    team_count: int
    ledger_count: int
    project_count: int
    pending_binding_request_count: int


def _require_super_admin(current_user: User) -> None:
    try:
        platform_permission_service.require_super_admin(current_user)
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("/overview", response_model=SuperAdminOverviewResponse)
def get_super_admin_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SuperAdminOverviewResponse:
    _require_super_admin(current_user)
    return SuperAdminOverviewResponse(
        user_count=db.query(User).count(),
        team_count=db.query(Team).count(),
        ledger_count=db.query(Ledger).count(),
        project_count=db.query(Project).count(),
        pending_binding_request_count=db.query(BindingRequest).filter(BindingRequest.status == "pending").count(),
    )


@router.get("/binding-requests", response_model=list[BindingRequestResponse])
def list_super_admin_binding_requests(
    request_status: str = Query(default="pending", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BindingRequestResponse]:
    _require_super_admin(current_user)
    query = db.query(BindingRequest).order_by(BindingRequest.created_at.desc())
    if request_status != "all":
        if request_status not in {"pending", "approved", "rejected"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status 只能是 pending、approved、rejected 或 all")
        query = query.filter(BindingRequest.status == request_status)
    return [build_binding_request_response(attach_display_names(db, request)) for request in query.all()]
