from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Entity
from app.services.entity_management_service import EntityManagementService

router = APIRouter(prefix="/api/entities", tags=["entities"])


class EntityTagPayload(BaseModel):
    tag: str
    tag_type: str = "name"
    confidence: float = 0.8


class EntityCreatePayload(BaseModel):
    entity_name: str
    entity_code: str | None = None
    ledger_id: int | None = None
    entity_type: str = "company"
    entity_category: str = "parent"
    is_accounting_entity: bool = False
    is_tax_entity: bool = False
    is_legal_entity: bool = False
    is_management_entity: bool = False
    legal_form: str | None = None
    has_legal_personality: bool = True
    tax_registration_no: str | None = None
    taxpayer_type: str | None = None
    parent_id: int | None = None
    hierarchy_level: int = 1
    valid_from: date | None = None
    valid_to: date | None = None
    tags: list[EntityTagPayload] = []


class TagPayload(BaseModel):
    tag: str
    tag_type: str = "name"
    confidence: float = 0.8


class VirtualSetCreatePayload(BaseModel):
    set_name: str
    set_type: str = "group"
    description: str | None = None


class ScopeCreatePayload(BaseModel):
    scope_name: str
    period_start: date
    period_end: date
    scope_type: str = "consolidation"


class ScopeMemberPayload(BaseModel):
    entity_id: int
    member_type: str = "full"
    ownership_percentage: float | None = None


class ConfusionPayload(BaseModel):
    contract_entity_name: str
    invoice_entity_name: str


def _entity_to_dict(entity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "entity_name": entity.entity_name,
        "entity_code": entity.entity_code,
        "ledger_id": entity.ledger_id,
        "entity_type": entity.entity_type,
        "entity_category": entity.entity_category,
        "is_accounting_entity": entity.is_accounting_entity,
        "is_tax_entity": entity.is_tax_entity,
        "is_legal_entity": entity.is_legal_entity,
        "is_management_entity": entity.is_management_entity,
        "legal_form": entity.legal_form,
        "has_legal_personality": entity.has_legal_personality,
        "tax_registration_no": entity.tax_registration_no,
        "taxpayer_type": entity.taxpayer_type,
        "parent_id": entity.parent_id,
        "hierarchy_level": entity.hierarchy_level,
        "is_active": entity.is_active,
    }


@router.post("")
def create_entity(payload: EntityCreatePayload, db: Session = Depends(get_db)) -> dict:
    service = EntityManagementService(db)
    entity = service.create_entity(payload.model_dump())
    return _entity_to_dict(entity)


@router.get("")
def list_entities(
    entity_type: str | None = None,
    accounting_entity: bool | None = None,
    tax_entity: bool | None = None,
    legal_entity: bool | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    service = EntityManagementService(db)
    items = service.get_entities_by_type(
        entity_type=entity_type,
        accounting_entity=accounting_entity,
        tax_entity=tax_entity,
        legal_entity=legal_entity,
    )
    return [_entity_to_dict(e) for e in items]


@router.get("/search")
def search_entity(name: str, db: Session = Depends(get_db)) -> list[dict]:
    service = EntityManagementService(db)
    items = service.find_entity_by_name(name)
    return [_entity_to_dict(e) for e in items]


@router.post("/{entity_id}/tags")
def add_tag(entity_id: int, payload: TagPayload, db: Session = Depends(get_db)) -> dict:
    service = EntityManagementService(db)
    if not db.get(Entity, entity_id):
        raise HTTPException(status_code=404, detail="主体不存在")
    service.add_entity_tag(entity_id, payload.tag, payload.tag_type, payload.confidence)
    return {"entity_id": entity_id, "tag": payload.tag}


@router.get("/{entity_id}/hierarchy")
def get_hierarchy(entity_id: int, db: Session = Depends(get_db)) -> list[dict]:
    service = EntityManagementService(db)
    items = service.get_entity_hierarchy(entity_id)
    if not items:
        raise HTTPException(status_code=404, detail="主体不存在")
    return [_entity_to_dict(e) for e in items]


@router.post("/virtual-sets")
def create_virtual_set(payload: VirtualSetCreatePayload, db: Session = Depends(get_db)) -> dict:
    service = EntityManagementService(db)
    vs = service.create_virtual_set(payload.set_name, payload.set_type, payload.description)
    return {"id": vs.id, "set_name": vs.set_name, "set_type": vs.set_type}


@router.post("/virtual-sets/{set_id}/members/{entity_id}")
def add_virtual_set_member(
    set_id: int,
    entity_id: int,
    member_role: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    service = EntityManagementService(db)
    service.add_entity_to_virtual_set(set_id, entity_id, member_role)
    return {"set_id": set_id, "entity_id": entity_id}


@router.get("/virtual-sets/{set_id}/members")
def list_virtual_set_members(set_id: int, db: Session = Depends(get_db)) -> list[dict]:
    service = EntityManagementService(db)
    items = service.get_virtual_set_members(set_id)
    return [_entity_to_dict(e) for e in items]


@router.post("/scopes")
def create_scope(payload: ScopeCreatePayload, db: Session = Depends(get_db)) -> dict:
    service = EntityManagementService(db)
    scope = service.create_scope(
        payload.scope_name, payload.period_start, payload.period_end, payload.scope_type
    )
    return {
        "id": scope.id,
        "scope_name": scope.scope_name,
        "period_start": scope.period_start.isoformat(),
        "period_end": scope.period_end.isoformat(),
        "scope_type": scope.scope_type,
    }


@router.post("/scopes/{scope_id}/members")
def add_scope_member(scope_id: int, payload: ScopeMemberPayload, db: Session = Depends(get_db)) -> dict:
    service = EntityManagementService(db)
    service.add_entity_to_scope(
        scope_id, payload.entity_id, payload.member_type, payload.ownership_percentage
    )
    return {"scope_id": scope_id, "entity_id": payload.entity_id}


@router.get("/scopes/{scope_id}/members")
def list_scope_members(scope_id: int, db: Session = Depends(get_db)) -> list[dict]:
    service = EntityManagementService(db)
    items = service.get_scope_entities(scope_id)
    return [_entity_to_dict(e) for e in items]


@router.post("/detect-confusion")
def detect_confusion(payload: ConfusionPayload, db: Session = Depends(get_db)) -> dict:
    service = EntityManagementService(db)
    return service.detect_entity_confusion(
        payload.contract_entity_name, payload.invoice_entity_name
    )
