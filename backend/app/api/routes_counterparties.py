from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import Counterparty
from app.db.session import get_db

router = APIRouter(prefix="/api/counterparties", tags=["counterparties"])


VALID_ROLES = {
    "customer",
    "supplier",
    "related_party",
    "government",
    "individual",
    "internal",
    "other",
}


class CounterpartyCreate(BaseModel):
    name: str
    role: str = "other"
    unified_credit_no: str | None = None
    is_related_party: bool = False
    default_entity_id: int | None = None


class CounterpartyUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    unified_credit_no: str | None = None
    is_related_party: bool | None = None
    default_entity_id: int | None = None


class CounterpartyBatchRequest(BaseModel):
    ids: list[int]


class CounterpartyBatchRoleUpdate(BaseModel):
    ids: list[int]
    role: str


def _to_dict(cp: Counterparty) -> dict[str, Any]:
    return {
        "id": cp.id,
        "name": cp.name,
        "role": cp.role,
        "unified_credit_no": cp.unified_credit_no,
        "is_related_party": cp.is_related_party,
        "default_entity_id": cp.default_entity_id,
        "is_active": cp.is_active,
    }


@router.get("")
def list_counterparties(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    try:
        items = db.query(Counterparty).order_by(Counterparty.id).all()
        return [_to_dict(cp) for cp in items]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=422, detail=f"往来单位加载失败，请检查基础资料表结构或迁移状态：{exc}")


@router.post("/batch")
def get_counterparties_batch(
    payload: CounterpartyBatchRequest,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    批量查询往来单位详情。

    业务场景：
        导入结果页等需要一次性展示多条分录关联的往来单位信息，
        避免逐条发起的 N+1 查询。
    """
    try:
        if not payload.ids:
            return []
        unique_ids = list(set(payload.ids))
        items = db.query(Counterparty).filter(Counterparty.id.in_(unique_ids)).all()
        return [_to_dict(cp) for cp in items]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=422, detail=f"往来单位批量查询失败：{exc}")


@router.post("/batch-update-role")
def batch_update_counterparty_role(
    payload: CounterpartyBatchRoleUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """批量变更往来单位角色（维度值主数据页初始归类用）。"""
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"角色无效，应为 {sorted(VALID_ROLES)}")
    unique_ids = list({i for i in payload.ids if i})
    if not unique_ids:
        raise HTTPException(status_code=400, detail="请至少选择一条往来单位")
    try:
        items = (
            db.query(Counterparty)
            .filter(Counterparty.id.in_(unique_ids), Counterparty.is_active == True)
            .all()
        )
        if not items:
            raise HTTPException(status_code=404, detail="未找到可更新的往来单位")
        for cp in items:
            cp.role = payload.role
            if payload.role == "related_party":
                cp.is_related_party = True
        db.commit()
        for cp in items:
            db.refresh(cp)
        return {
            "updated": len(items),
            "role": payload.role,
            "items": [_to_dict(cp) for cp in items],
            "skipped_ids": [i for i in unique_ids if i not in {cp.id for cp in items}],
        }
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"批量更新角色失败：{exc}")


@router.post("")
def create_counterparty(payload: CounterpartyCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"角色无效，应为 {sorted(VALID_ROLES)}")
    cp = Counterparty(**payload.model_dump())
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return _to_dict(cp)


@router.put("/{cp_id}")
def update_counterparty(cp_id: int, payload: CounterpartyUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    cp = db.get(Counterparty, cp_id)
    if not cp:
        raise HTTPException(status_code=404, detail="对方单位不存在")
    if payload.role is not None and payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"角色无效，应为 {sorted(VALID_ROLES)}")
    for key, value in payload.model_dump().items():
        if value is not None:
            setattr(cp, key, value)
    db.commit()
    db.refresh(cp)
    return _to_dict(cp)


@router.post("/{cp_id}/disable")
def disable_counterparty(cp_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    cp = db.get(Counterparty, cp_id)
    if not cp:
        raise HTTPException(status_code=404, detail="对方单位不存在")
    cp.is_active = False
    db.commit()
    db.refresh(cp)
    return _to_dict(cp)
