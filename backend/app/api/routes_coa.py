from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.basic_data import coa_service

router = APIRouter(prefix="/api/coa", tags=["chart-of-accounts"])


class CoACreate(BaseModel):
    code: str
    name: str
    parent_code: str | None = None
    level: int = 1
    category: str
    direction: str
    account_category: str | None = None
    account_subcategory: str | None = None
    equity_subcategory: str | None = None
    include_in_dividend_base: bool | None = None
    is_terminal: bool = True


class CoAUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    direction: str | None = None
    account_category: str | None = None
    account_subcategory: str | None = None
    equity_subcategory: str | None = None
    include_in_dividend_base: bool | None = None
    parent_code: str | None = None
    is_terminal: bool | None = None


def _to_dict(account: Any) -> dict[str, Any]:
    return {
        "code": account.code,
        "name": account.name,
        "parent_code": account.parent_code,
        "level": account.level,
        "category": account.category,
        "direction": account.direction,
        "account_category": account.account_category,
        "account_subcategory": account.account_subcategory,
        "equity_subcategory": account.equity_subcategory,
        "include_in_dividend_base": account.include_in_dividend_base,
        "is_terminal": account.is_terminal,
        "status": account.status,
        "is_system": account.is_system,
    }


@router.get("")
def list_accounts(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    try:
        return [_to_dict(a) for a in coa_service.list_accounts(db)]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=422, detail=f"会计科目加载失败，请检查基础资料表结构或迁移状态：{exc}")


@router.get("/industry-templates")
def list_industry_templates() -> list[dict[str, Any]]:
    return coa_service.list_industry_templates()


@router.get("/industry-templates/{template_code}")
def preview_industry_template(template_code: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return coa_service.preview_industry_template(db, template_code)
    except LookupError:
        raise HTTPException(status_code=404, detail="行业科目模板不存在")


@router.post("/industry-templates/{template_code}/import")
def import_industry_template(template_code: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return coa_service.import_industry_template(db, template_code)
    except LookupError:
        raise HTTPException(status_code=404, detail="行业科目模板不存在")


@router.post("")
def create_account(payload: CoACreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        account = coa_service.create_account(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_dict(account)


@router.put("/{code}")
def update_account(code: str, payload: CoAUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        account = coa_service.update_account(
            db, code, {k: v for k, v in payload.model_dump().items() if v is not None}
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="科目不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_dict(account)


@router.post("/{code}/disable")
def disable_account(code: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        account = coa_service.set_status(db, code, "disabled")
    except LookupError:
        raise HTTPException(status_code=404, detail="科目不存在")
    return _to_dict(account)


@router.post("/{code}/archive")
def archive_account(code: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        account = coa_service.set_status(db, code, "archived")
    except LookupError:
        raise HTTPException(status_code=404, detail="科目不存在")
    return _to_dict(account)


@router.delete("/{code}")
def delete_account(code: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        coa_service.delete_account(db, code)
    except LookupError:
        raise HTTPException(status_code=404, detail="科目不存在")
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deleted": code}
