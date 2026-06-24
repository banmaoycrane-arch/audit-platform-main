from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import workpaper_service

router = APIRouter(prefix="/api/workpapers", tags=["workpapers"])


def require_ledger(ledger_id: int | None = Depends(get_current_ledger)) -> int:
    if ledger_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择账套")
    return ledger_id


class WorkpaperVersionResponse(BaseModel):
    id: int
    workpaper_index_id: int
    source_file_id: int
    filename: str | None
    version_no: str
    status: str
    status_label: str
    prepared_by: int | None
    reviewed_by: int | None
    change_reason: str | None
    supersedes_id: int | None
    created_at: str | None


class WorkpaperIndexResponse(BaseModel):
    id: int
    ledger_id: int
    project_id: int | None
    parent_id: int | None
    index_no: str
    title: str
    audit_area: str | None
    archive_path: str | None
    source_module_key: str | None
    sort_order: int
    version_count: int
    current_version_no: str | None
    current_status: str | None
    created_at: str | None
    versions: list[WorkpaperVersionResponse] = []


class CreateWorkpaperIndexRequest(BaseModel):
    title: str
    audit_area: str | None = None
    project_id: int | None = None
    parent_id: int | None = None
    index_no: str | None = None
    archive_path: str | None = None
    source_module_key: str | None = None


class RegisterSourceFileRequest(BaseModel):
    source_file_id: int


class ReviseWorkpaperRequest(BaseModel):
    source_file_id: int
    change_reason: str = Field(min_length=1)


class UpdateVersionStatusRequest(BaseModel):
    status: str


class WorkpaperCatalogResponse(BaseModel):
    ledger_id: int
    exported_at: str
    index_count: int
    version_count: int
    items: list[WorkpaperIndexResponse]


@router.get("/index", response_model=list[WorkpaperIndexResponse])
def list_workpaper_index(
    project_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> list[WorkpaperIndexResponse]:
    rows = workpaper_service.list_workpaper_indexes(db, ledger_id, project_id=project_id)
    return [WorkpaperIndexResponse.model_validate(row) for row in rows]


@router.post("/index", response_model=WorkpaperIndexResponse, status_code=status.HTTP_201_CREATED)
def create_workpaper_index(
    payload: CreateWorkpaperIndexRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> WorkpaperIndexResponse:
    row = workpaper_service.create_index_node(
        db,
        ledger_id,
        title=payload.title,
        audit_area=payload.audit_area,
        project_id=payload.project_id,
        parent_id=payload.parent_id,
        index_no=payload.index_no,
        archive_path=payload.archive_path,
        source_module_key=payload.source_module_key,
    )
    return WorkpaperIndexResponse.model_validate(row)


@router.get("/index/{index_id}", response_model=WorkpaperIndexResponse)
def get_workpaper_index(
    index_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> WorkpaperIndexResponse:
    row = workpaper_service.get_workpaper_index(db, index_id, ledger_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="底稿索引不存在")
    return WorkpaperIndexResponse.model_validate(row)


@router.post("/register", response_model=WorkpaperIndexResponse, status_code=status.HTTP_201_CREATED)
def register_workpaper_from_source_file(
    payload: RegisterSourceFileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> WorkpaperIndexResponse:
    try:
        row = workpaper_service.register_source_file(
            db,
            ledger_id,
            payload.source_file_id,
            prepared_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkpaperIndexResponse.model_validate(row)


@router.post("/sync-from-archive", response_model=list[WorkpaperIndexResponse])
def sync_workpapers_from_archive(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> list[WorkpaperIndexResponse]:
    rows = workpaper_service.sync_from_archived_files(db, ledger_id, prepared_by=current_user.id)
    return [WorkpaperIndexResponse.model_validate(row) for row in rows]


@router.post("/index/{index_id}/revise", response_model=WorkpaperIndexResponse)
def revise_workpaper_index(
    index_id: int,
    payload: ReviseWorkpaperRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> WorkpaperIndexResponse:
    try:
        row = workpaper_service.revise_workpaper(
            db,
            index_id,
            ledger_id,
            source_file_id=payload.source_file_id,
            change_reason=payload.change_reason,
            prepared_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkpaperIndexResponse.model_validate(row)


@router.patch("/versions/{version_id}", response_model=WorkpaperVersionResponse)
def update_workpaper_version_status(
    version_id: int,
    payload: UpdateVersionStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> WorkpaperVersionResponse:
    try:
        row = workpaper_service.update_version_status(
            db,
            version_id,
            ledger_id,
            status=payload.status,
            reviewed_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkpaperVersionResponse.model_validate(row)


@router.get("/export", response_model=WorkpaperCatalogResponse)
def export_workpaper_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ledger_id: int = Depends(require_ledger),
) -> WorkpaperCatalogResponse:
    row = workpaper_service.export_workpaper_catalog(db, ledger_id)
    return WorkpaperCatalogResponse.model_validate(row)
