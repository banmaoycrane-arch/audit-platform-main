from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import Industry, Material
from app.db.session import get_db
from app.services.accounting_unit_service import AccountingUnitService

router = APIRouter(prefix="/api/materials", tags=["materials"])


class MaterialCreate(BaseModel):
    material_code: str
    material_name: str
    material_type: str
    industry_id: Optional[int] = None
    parent_id: Optional[int] = None
    unit: Optional[str] = None
    specification: Optional[str] = None


class BOMCreate(BaseModel):
    parent_material_id: int
    child_material_id: int
    quantity: float
    loss_rate: Optional[float] = None


def _industry_to_dict(industry: Industry) -> dict[str, Any]:
    return {
        "id": industry.id,
        "industry_code": industry.industry_code,
        "industry_name": industry.industry_name,
        "industry_description": industry.industry_description,
        "recommended_granularity": industry.recommended_granularity,
        "granularity_description": industry.granularity_description,
        "supported_unit_types": industry.supported_unit_types,
    }


def _material_to_dict(material: Material) -> dict[str, Any]:
    return {
        "id": material.id,
        "material_code": material.material_code,
        "material_name": material.material_name,
        "material_type": material.material_type,
        "specification": material.specification,
        "unit": material.unit,
        "parent_id": material.parent_id,
        "hierarchy_level": material.hierarchy_level,
        "is_active": material.is_active,
    }


@router.post("/industries/initialize")
def initialize_industries(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    service = AccountingUnitService(db)
    industries = service.initialize_default_industries()
    return [_industry_to_dict(industry) for industry in industries]


@router.get("/industries")
def list_industries(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    industries = db.query(Industry).order_by(Industry.id).all()
    return [_industry_to_dict(industry) for industry in industries]


@router.get("/industries/recommend-granularity")
def recommend_granularity(
    industry: str = Query(...), db: Session = Depends(get_db)
) -> dict[str, Any]:
    service = AccountingUnitService(db)
    return service.recommend_granularity(industry)


@router.post("/")
def create_material(payload: MaterialCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = AccountingUnitService(db)
    try:
        material = service.create_material(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _material_to_dict(material)


@router.get("/")
def list_materials(
    material_type: Optional[str] = Query(None), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    query = db.query(Material).filter(Material.is_active == True)
    if material_type:
        query = query.filter(Material.material_type == material_type)
    materials = query.order_by(Material.id).all()
    return [_material_to_dict(material) for material in materials]


@router.post("/bom")
def create_bom(payload: BOMCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = AccountingUnitService(db)
    try:
        item = service.create_bom(
            parent_material_id=payload.parent_material_id,
            child_material_id=payload.child_material_id,
            quantity=payload.quantity,
            loss_rate=payload.loss_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "bom_item_id": item.id,
        "bom_id": item.bom_id,
        "parent_material_id": payload.parent_material_id,
        "child_material_id": item.material_id,
        "quantity": float(item.quantity),
        "unit": item.unit,
        "loss_rate": float(item.wastage_rate) if item.wastage_rate is not None else None,
    }


@router.get("/{material_id}/bom")
def get_material_bom(material_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    service = AccountingUnitService(db)
    bom = service.get_material_bom(material_id)
    if not bom:
        raise HTTPException(status_code=404, detail="物料不存在")
    return bom


@router.get("/{material_id}")
def get_material(material_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    return _material_to_dict(material)
