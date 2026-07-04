from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import (
    AccountingUnit,
    AccountingUnitCombinationMember,
    AccountingUnitType,
)
from app.db.session import get_db
from app.services.basic_data.accounting_unit_service import AccountingUnitService

router = APIRouter(prefix="/api/accounting-units", tags=["accounting-units"])


class AccountingUnitCreatePayload(BaseModel):
    unit_name: str
    unit_type_code: str
    parent_id: int | None = None
    description: str | None = None


class MergePayload(BaseModel):
    unit_ids: list[int]
    combination_name: str
    combination_type: str = "merged"


class VersionPayload(BaseModel):
    version_name: str
    effective_date: date
    changes: dict[str, Any]
    change_reason: str | None = None
    changed_by: str = "system"


def _type_to_dict(unit_type: AccountingUnitType) -> dict[str, Any]:
    return {
        "id": unit_type.id,
        "type_code": unit_type.type_code,
        "type_name": unit_type.type_name,
        "type_description": unit_type.type_description,
        "allow_hierarchy": unit_type.allow_hierarchy,
        "allow_combination": unit_type.allow_combination,
        "created_at": unit_type.created_at.isoformat(),
    }


def _unit_to_dict(unit: AccountingUnit) -> dict[str, Any]:
    return {
        "id": unit.id,
        "unit_name": unit.unit_name,
        "unit_code": unit.unit_code,
        "unit_type_id": unit.unit_type_id,
        "description": unit.description,
        "is_active": unit.is_active,
        "valid_from": unit.valid_from.isoformat() if unit.valid_from else None,
        "valid_to": unit.valid_to.isoformat() if unit.valid_to else None,
        "parent_id": unit.parent_id,
        "hierarchy_level": unit.hierarchy_level,
        "created_at": unit.created_at.isoformat(),
        "updated_at": unit.updated_at.isoformat(),
    }


def _combination_to_dict(combination: Any, db: Session) -> dict[str, Any]:
    members = db.query(AccountingUnitCombinationMember).filter(
        AccountingUnitCombinationMember.combination_id == combination.id
    ).order_by(AccountingUnitCombinationMember.priority).all()
    return {
        "id": combination.id,
        "combination_name": combination.combination_name,
        "combination_code": combination.combination_code,
        "combination_type": combination.combination_type,
        "is_active": combination.is_active,
        "created_at": combination.created_at.isoformat(),
        "updated_at": combination.updated_at.isoformat(),
        "members": [
            {
                "id": member.id,
                "unit_id": member.unit_id,
                "weight": float(member.weight),
                "priority": member.priority,
                "is_active": member.is_active,
            }
            for member in members
        ],
    }


def _version_to_dict(version: Any) -> dict[str, Any]:
    return {
        "id": version.id,
        "unit_id": version.unit_id,
        "version_number": version.version_number,
        "version_name": version.version_name,
        "effective_date": version.effective_date.isoformat(),
        "changes": version.changes,
        "change_reason": version.change_reason,
        "changed_by": version.changed_by,
        "created_at": version.created_at.isoformat(),
    }


@router.post("/types/initialize")
def initialize_types(db: Session = Depends(get_db)) -> dict[str, Any]:
    service = AccountingUnitService(db)
    service.initialize_default_types()
    count = db.query(AccountingUnitType).count()
    return {"ok": True, "count": count}


@router.get("/types")
def list_types(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    items = db.query(AccountingUnitType).order_by(AccountingUnitType.id).all()
    return [_type_to_dict(item) for item in items]


@router.post("/")
def create_unit(payload: AccountingUnitCreatePayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = AccountingUnitService(db)
    try:
        unit = service.create_unit(
            payload.unit_name,
            payload.unit_type_code,
            payload.parent_id,
            payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _unit_to_dict(unit)


@router.get("/")
def list_units(keyword: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    service = AccountingUnitService(db)
    items = service.search_units(keyword) if keyword else service.get_units_by_type()
    return [_unit_to_dict(item) for item in items]


@router.get("/{unit_id}")
def get_unit(unit_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    unit = db.get(AccountingUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="核算单位不存在")
    return _unit_to_dict(unit)


@router.post("/merge")
def merge_units(payload: MergePayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = AccountingUnitService(db)
    try:
        combination = service.merge_units(
            payload.unit_ids,
            payload.combination_name,
            payload.combination_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _combination_to_dict(combination, db)


@router.post("/combinations/{combination_id}/split")
def split_combination(combination_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = AccountingUnitService(db)
    try:
        result = service.split_combination(combination_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, **result}


@router.post("/{unit_id}/versions")
def create_version(unit_id: int, payload: VersionPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = AccountingUnitService(db)
    try:
        version = service.create_version(
            unit_id,
            payload.version_name,
            payload.effective_date,
            payload.changes,
            payload.change_reason,
            payload.changed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _version_to_dict(version)


@router.get("/{unit_id}/versions")
def get_versions(unit_id: int, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    if not db.get(AccountingUnit, unit_id):
        raise HTTPException(status_code=404, detail="核算单位不存在")
    service = AccountingUnitService(db)
    return [_version_to_dict(version) for version in service.get_versions(unit_id)]
