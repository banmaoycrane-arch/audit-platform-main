from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import coa_service

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


def _to_dict(account) -> dict[str, Any]:
    return {
        "ledger_id": account.ledger_id,
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


def _resolve_ledger_id(ledger_id: int | None, x_ledger_id: int | None) -> int | None:
    return ledger_id if ledger_id is not None else x_ledger_id


@router.get("")
def list_accounts(
    ledger_id: int | None = None,
    x_ledger_id: int | None = Header(None, alias="X-Ledger-Id"),
    db: Session = Depends(get_db),
) -> list[dict]:
    try:
        return [_to_dict(a) for a in coa_service.list_accounts(db, _resolve_ledger_id(ledger_id, x_ledger_id))]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=422, detail=f"会计科目加载失败，请检查基础资料表结构或迁移状态：{exc}")


@router.get("/industry-templates")
def list_industry_templates() -> list[dict]:
    return coa_service.list_industry_templates()


@router.get("/industry-templates/{template_code}")
def preview_industry_template(
    template_code: str,
    ledger_id: int | None = None,
    x_ledger_id: int | None = Header(None, alias="X-Ledger-Id"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return coa_service.preview_industry_template(db, template_code, _resolve_ledger_id(ledger_id, x_ledger_id))
    except LookupError:
        raise HTTPException(status_code=404, detail="行业科目模板不存在")


@router.post("/industry-templates/{template_code}/import")
def import_industry_template(
    template_code: str,
    ledger_id: int | None = None,
    x_ledger_id: int | None = Header(None, alias="X-Ledger-Id"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return coa_service.import_industry_template(db, template_code, _resolve_ledger_id(ledger_id, x_ledger_id))
    except LookupError:
        raise HTTPException(status_code=404, detail="行业科目模板不存在")


@router.post("")
def create_account(
    payload: CoACreate,
    ledger_id: int | None = None,
    x_ledger_id: int | None = Header(None, alias="X-Ledger-Id"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        account = coa_service.create_account(db, payload.model_dump(), _resolve_ledger_id(ledger_id, x_ledger_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_dict(account)


@router.put("/{code}")
def update_account(
    code: str,
    payload: CoAUpdate,
    ledger_id: int | None = None,
    x_ledger_id: int | None = Header(None, alias="X-Ledger-Id"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        account = coa_service.update_account(
            db,
            code,
            {k: v for k, v in payload.model_dump().items() if v is not None},
            _resolve_ledger_id(ledger_id, x_ledger_id),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="科目不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_dict(account)


@router.post("/{code}/disable")
def disable_account(
    code: str,
    ledger_id: int | None = None,
    x_ledger_id: int | None = Header(None, alias="X-Ledger-Id"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        account = coa_service.set_status(db, code, "disabled", _resolve_ledger_id(ledger_id, x_ledger_id))
    except LookupError:
        raise HTTPException(status_code=404, detail="科目不存在")
    return _to_dict(account)


@router.post("/{code}/archive")
def archive_account(
    code: str,
    ledger_id: int | None = None,
    x_ledger_id: int | None = Header(None, alias="X-Ledger-Id"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        account = coa_service.set_status(db, code, "archived", _resolve_ledger_id(ledger_id, x_ledger_id))
    except LookupError:
        raise HTTPException(status_code=404, detail="科目不存在")
    return _to_dict(account)


@router.delete("/{code}")
def delete_account(
    code: str,
    ledger_id: int | None = None,
    x_ledger_id: int | None = Header(None, alias="X-Ledger-Id"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        coa_service.delete_account(db, code, _resolve_ledger_id(ledger_id, x_ledger_id))
    except LookupError:
        raise HTTPException(status_code=404, detail="科目不存在")
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deleted": code}
