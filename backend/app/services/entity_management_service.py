from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.models import (
    Entity, EntityTag, EntityScope, EntityScopeMember, EntityVersion,
    VirtualEntitySet, VirtualEntitySetMember, EntityRelationType, EntityRelation
)


class EntityManagementService:
    def __init__(self, db: Session):
        self.db = db

    def create_entity(self, entity_data: Dict[str, Any]) -> Entity:
        """创建主体"""
        entity = Entity(
            entity_name=entity_data["entity_name"],
            entity_code=entity_data.get("entity_code"),
            entity_type=entity_data.get("entity_type", "company"),
            entity_category=entity_data.get("entity_category", "parent"),
            
            # 多维度主体类型
            is_accounting_entity=entity_data.get("is_accounting_entity", False),
            is_tax_entity=entity_data.get("is_tax_entity", False),
            is_legal_entity=entity_data.get("is_legal_entity", False),
            is_management_entity=entity_data.get("is_management_entity", False),
            
            # 法律属性
            legal_form=entity_data.get("legal_form"),
            has_legal_personality=entity_data.get("has_legal_personality", True),
            
            # 税务属性
            tax_registration_no=entity_data.get("tax_registration_no"),
            taxpayer_type=entity_data.get("taxpayer_type"),
            
            # 层级关系
            parent_id=entity_data.get("parent_id"),
            hierarchy_level=entity_data.get("hierarchy_level", 1),
            ledger_id=entity_data.get("ledger_id"),
            
            # 时间范围
            valid_from=entity_data.get("valid_from"),
            valid_to=entity_data.get("valid_to")
        )
        
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        
        # 添加语义标签
        for tag in entity_data.get("tags", []):
            self.add_entity_tag(entity.id, tag["tag"], tag.get("tag_type", "name"))
        
        return entity

    def add_entity_tag(self, entity_id: int, tag: str, tag_type: str = "name", confidence: float = 0.8):
        """添加主体语义标签"""
        existing = self.db.query(EntityTag).filter(
            EntityTag.entity_id == entity_id,
            EntityTag.tag == tag
        ).first()
        
        if not existing:
            entity_tag = EntityTag(
                entity_id=entity_id,
                tag=tag,
                tag_type=tag_type,
                confidence=confidence
            )
            self.db.add(entity_tag)
            self.db.commit()

    def find_entity_by_name(self, entity_name: str) -> List[Entity]:
        """通过语义匹配查找主体"""
        # 首先精确匹配
        exact_match = self.db.query(Entity).filter(
            Entity.entity_name == entity_name
        ).all()
        
        if exact_match:
            return exact_match
        
        # 然后通过标签模糊匹配
        tags = self.db.query(EntityTag).filter(
            EntityTag.tag.ilike(f"%{entity_name}%")
        ).all()
        
        entity_ids = [t.entity_id for t in tags]
        return self.db.query(Entity).filter(Entity.id.in_(entity_ids)).all()

    def create_virtual_set(self, set_name: str, set_type: str = "group", description: Optional[str] = None) -> VirtualEntitySet:
        """创建虚拟主体集合"""
        virtual_set = VirtualEntitySet(
            set_name=set_name,
            set_type=set_type,
            set_description=description
        )
        
        self.db.add(virtual_set)
        self.db.commit()
        self.db.refresh(virtual_set)
        
        return virtual_set

    def add_entity_to_virtual_set(self, set_id: int, entity_id: int, member_role: Optional[str] = None):
        """将主体添加到虚拟集合"""
        existing = self.db.query(VirtualEntitySetMember).filter(
            VirtualEntitySetMember.set_id == set_id,
            VirtualEntitySetMember.entity_id == entity_id
        ).first()
        
        if not existing:
            member = VirtualEntitySetMember(
                set_id=set_id,
                entity_id=entity_id,
                member_role=member_role
            )
            self.db.add(member)
            self.db.commit()

    def get_virtual_set_members(self, set_id: int) -> List[Entity]:
        """获取虚拟集合的所有成员"""
        members = self.db.query(VirtualEntitySetMember).filter(
            VirtualEntitySetMember.set_id == set_id,
            VirtualEntitySetMember.is_active == True
        ).all()
        
        entity_ids = [m.entity_id for m in members]
        return self.db.query(Entity).filter(Entity.id.in_(entity_ids)).all()

    def create_entity_relation(self, entity_a_id: int, entity_b_id: int, relation_type_code: str,
                              ownership_percentage: Optional[float] = None) -> EntityRelation:
        """创建主体关系"""
        relation_type = self.db.query(EntityRelationType).filter(
            EntityRelationType.relation_code == relation_type_code
        ).first()
        
        if not relation_type:
            raise ValueError(f"Relation type {relation_type_code} not found")
        
        relation = EntityRelation(
            entity_a_id=entity_a_id,
            entity_b_id=entity_b_id,
            relation_type_id=relation_type.id,
            ownership_percentage=ownership_percentage
        )
        
        self.db.add(relation)
        self.db.commit()
        self.db.refresh(relation)
        
        return relation

    def get_entity_relations(self, entity_id: int) -> List[EntityRelation]:
        """获取主体的所有关系"""
        return self.db.query(EntityRelation).filter(
            or_(
                EntityRelation.entity_a_id == entity_id,
                EntityRelation.entity_b_id == entity_id
            ),
            EntityRelation.is_active == True
        ).all()

    def detect_entity_confusion(self, contract_entity_name: str, invoice_entity_name: str) -> Dict[str, Any]:
        """检测主体定义混淆风险"""
        contract_entities = self.find_entity_by_name(contract_entity_name)
        invoice_entities = self.find_entity_by_name(invoice_entity_name)
        
        # 检查是否存在关联关系
        has_relation = False
        relation_details = []
        
        for ce in contract_entities:
            for ie in invoice_entities:
                relations = self.db.query(EntityRelation).filter(
                    or_(
                        (EntityRelation.entity_a_id == ce.id) & (EntityRelation.entity_b_id == ie.id),
                        (EntityRelation.entity_a_id == ie.id) & (EntityRelation.entity_b_id == ce.id)
                    ),
                    EntityRelation.is_active == True
                ).all()
                
                if relations:
                    has_relation = True
                    relation_details.extend([{
                        "relation_id": r.id,
                        "relation_code": self._get_relation_code(r.relation_type_id),
                        "ownership_percentage": r.ownership_percentage
                    } for r in relations])
        
        # 判断风险级别
        if contract_entities and invoice_entities:
            if has_relation:
                return {
                    "risk_level": "low",
                    "risk_type": "entity_confusion",
                    "description": "合同主体与发票主体存在关联关系，风险较低",
                    "relation_details": relation_details
                }
            else:
                return {
                    "risk_level": "medium",
                    "risk_type": "entity_confusion",
                    "description": "合同主体与发票主体不一致且无关联关系，请核实",
                    "contract_entities": [e.entity_name for e in contract_entities],
                    "invoice_entities": [e.entity_name for e in invoice_entities]
                }
        else:
            return {
                "risk_level": "high",
                "risk_type": "entity_confusion",
                "description": "无法识别合同主体或发票主体，请确认主体信息",
                "contract_entity_name": contract_entity_name,
                "invoice_entity_name": invoice_entity_name
            }

    def _get_relation_code(self, relation_type_id: int) -> Optional[str]:
        """获取关系类型代码"""
        relation_type = self.db.query(EntityRelationType).filter(
            EntityRelationType.id == relation_type_id
        ).first()
        return relation_type.relation_code if relation_type else None

    def initialize_default_relation_types(self):
        """初始化默认关系类型"""
        default_types = [
            {"relation_code": "parent_subsidiary", "relation_name": "母子公司关系"},
            {"relation_code": "branch_of", "relation_name": "分支机构关系"},
            {"relation_code": "same_control", "relation_name": "同一控制关系"},
            {"relation_code": "associate", "relation_name": "联营企业关系"},
            {"relation_code": "joint_venture", "relation_name": "合营企业关系"},
            {"relation_code": "shareholder", "relation_name": "股东关系"},
            {"relation_code": "management", "relation_name": "管理关系"},
            {"relation_code": "related_party", "relation_name": "关联方关系"}
        ]
        
        for rt in default_types:
            existing = self.db.query(EntityRelationType).filter(
                EntityRelationType.relation_code == rt["relation_code"]
            ).first()
            if not existing:
                relation_type = EntityRelationType(**rt)
                self.db.add(relation_type)
        
        self.db.commit()

    def create_scope(self, scope_name: str, period_start: date, period_end: date,
                     scope_type: str = "consolidation") -> EntityScope:
        """创建主体范围"""
        scope = EntityScope(
            scope_name=scope_name,
            period_start=period_start,
            period_end=period_end,
            scope_type=scope_type
        )
        
        self.db.add(scope)
        self.db.commit()
        self.db.refresh(scope)
        
        return scope

    def add_entity_to_scope(self, scope_id: int, entity_id: int, member_type: str = "full",
                           ownership_percentage: Optional[float] = None):
        """将主体添加到范围"""
        existing = self.db.query(EntityScopeMember).filter(
            EntityScopeMember.scope_id == scope_id,
            EntityScopeMember.entity_id == entity_id
        ).first()
        
        if not existing:
            member = EntityScopeMember(
                scope_id=scope_id,
                entity_id=entity_id,
                member_type=member_type,
                ownership_percentage=ownership_percentage
            )
            self.db.add(member)
            self.db.commit()

    def get_scope_entities(self, scope_id: int) -> List[Entity]:
        """获取范围包含的所有主体"""
        members = self.db.query(EntityScopeMember).filter(
            EntityScopeMember.scope_id == scope_id,
            EntityScopeMember.is_included == True
        ).all()
        
        entity_ids = [m.entity_id for m in members]
        return self.db.query(Entity).filter(Entity.id.in_(entity_ids)).all()

    def get_entities_by_type(self, entity_type: Optional[str] = None,
                           accounting_entity: Optional[bool] = None,
                           tax_entity: Optional[bool] = None,
                           legal_entity: Optional[bool] = None) -> List[Entity]:
        """按类型筛选主体"""
        query = self.db.query(Entity).filter(Entity.is_active == True)
        
        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)
        if accounting_entity is not None:
            query = query.filter(Entity.is_accounting_entity == accounting_entity)
        if tax_entity is not None:
            query = query.filter(Entity.is_tax_entity == tax_entity)
        if legal_entity is not None:
            query = query.filter(Entity.is_legal_entity == legal_entity)
        
        return query.all()

    def get_entity_hierarchy(self, entity_id: int) -> List[Entity]:
        """获取主体的层级关系链"""
        hierarchy = []
        current = self.db.query(Entity).filter(Entity.id == entity_id).first()
        
        while current:
            hierarchy.append(current)
            if current.parent_id:
                current = self.db.query(Entity).filter(Entity.id == current.parent_id).first()
            else:
                break
        
        return hierarchy