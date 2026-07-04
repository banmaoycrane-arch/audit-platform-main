from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.models import (
    AccountingUnit, AccountingUnitType, AccountingUnitHierarchy,
    AccountingUnitCombination, AccountingUnitCombinationMember,
    AccountingUnitEntityRelation, AccountingUnitVersion, AccountingUnitTag,
    Entity, Industry, Material, MaterialBOM, MaterialBOMItem
)


class AccountingUnitService:
    def __init__(self, db: Session):
        self.db = db

    def initialize_default_types(self) -> None:
        """初始化默认核算单位类型"""
        default_types = [
            {"type_code": "project", "type_name": "项目", "type_description": "工程项目、投资项目等"},
            {"type_code": "department", "type_name": "部门", "type_description": "企业内部部门"},
            {"type_code": "product", "type_name": "产品", "type_description": "产品、产品线"},
            {"type_code": "channel", "type_name": "渠道", "type_description": "销售渠道、分销渠道"},
            {"type_code": "customer", "type_name": "客户", "type_description": "客户、大客户"},
            {"type_code": "platform", "type_name": "平台", "type_description": "电商平台、业务平台"},
            {"type_code": "store", "type_name": "店铺", "type_description": "线下店铺、线上店铺"},
            {"type_code": "business_unit", "type_name": "业务单位", "type_description": "事业部、业务线"}
        ]
        
        for ut in default_types:
            existing = self.db.query(AccountingUnitType).filter(
                AccountingUnitType.type_code == ut["type_code"]
            ).first()
            if not existing:
                unit_type = AccountingUnitType(**ut)
                self.db.add(unit_type)
        
        self.db.commit()

    def create_unit(self, unit_name: str, unit_type_code: str, 
                   parent_id: Optional[int] = None, description: Optional[str] = None) -> AccountingUnit:
        """创建核算单位"""
        unit_type = self.db.query(AccountingUnitType).filter(
            AccountingUnitType.type_code == unit_type_code
        ).first()
        
        if not unit_type:
            raise ValueError(f"Unit type {unit_type_code} not found")
        
        hierarchy_level = 1
        if parent_id:
            parent = self.db.query(AccountingUnit).filter(AccountingUnit.id == parent_id).first()
            if parent:
                hierarchy_level = parent.hierarchy_level + 1
        
        unit = AccountingUnit(
            unit_name=unit_name,
            unit_type_id=unit_type.id,
            parent_id=parent_id,
            hierarchy_level=hierarchy_level,
            description=description
        )
        
        self.db.add(unit)
        self.db.commit()
        self.db.refresh(unit)
        
        # 如果有父级，建立层级关系
        if parent_id:
            self._create_hierarchy(parent_id, unit.id)
        
        return unit

    def _create_hierarchy(self, parent_id: int, child_id: int) -> None:
        """创建层级关系"""
        parent = self.db.query(AccountingUnit).filter(AccountingUnit.id == parent_id).first()
        
        hierarchy = AccountingUnitHierarchy(
            parent_unit_id=parent_id,
            child_unit_id=child_id,
            depth=parent.hierarchy_level if parent else 1
        )
        
        self.db.add(hierarchy)
        self.db.commit()

    def create_combination(self, combination_name: str, unit_ids: List[int], 
                          combination_type: str = "group") -> AccountingUnitCombination:
        """创建核算单位组合"""
        return self.merge_units(unit_ids, combination_name, combination_type)

    def merge_units(self, unit_ids: List[int], combination_name: str,
                    combination_type: str = "merged") -> AccountingUnitCombination:
        """合并多个核算单位为组合"""
        if not unit_ids:
            raise ValueError("unit_ids cannot be empty")

        units = self.db.query(AccountingUnit).filter(
            AccountingUnit.id.in_(unit_ids),
            AccountingUnit.is_active == True
        ).all()
        if len({u.id for u in units}) != len(set(unit_ids)):
            raise ValueError("Some units not found")

        combination = AccountingUnitCombination(
            combination_name=combination_name,
            combination_type=combination_type
        )

        self.db.add(combination)
        self.db.commit()
        self.db.refresh(combination)

        for i, unit_id in enumerate(unit_ids):
            member = AccountingUnitCombinationMember(
                combination_id=combination.id,
                unit_id=unit_id,
                priority=i + 1
            )
            self.db.add(member)

        self.db.commit()
        self.db.refresh(combination)

        return combination

    def split_combination(self, combination_id: int) -> Dict[str, Any]:
        """拆分核算单位组合"""
        combination = self.db.query(AccountingUnitCombination).filter(
            AccountingUnitCombination.id == combination_id
        ).first()
        if not combination:
            raise ValueError("Combination not found")

        members = self.db.query(AccountingUnitCombinationMember).filter(
            AccountingUnitCombinationMember.combination_id == combination_id,
            AccountingUnitCombinationMember.is_active == True
        ).all()
        member_unit_ids = [m.unit_id for m in members]

        combination.is_active = False
        for member in members:
            member.is_active = False
        self.db.commit()

        return {"combination_id": combination_id, "member_unit_ids": member_unit_ids}

    def add_to_combination(self, combination_id: int, unit_id: int, weight: float = 1.0) -> None:
        """添加核算单位到组合"""
        existing = self.db.query(AccountingUnitCombinationMember).filter(
            AccountingUnitCombinationMember.combination_id == combination_id,
            AccountingUnitCombinationMember.unit_id == unit_id
        ).first()
        
        if not existing:
            priority = self.db.query(AccountingUnitCombinationMember).filter(
                AccountingUnitCombinationMember.combination_id == combination_id
            ).count() + 1
            
            member = AccountingUnitCombinationMember(
                combination_id=combination_id,
                unit_id=unit_id,
                weight=weight,
                priority=priority
            )
            self.db.add(member)
            self.db.commit()

    def remove_from_combination(self, combination_id: int, unit_id: int) -> None:
        """从组合中移除核算单位"""
        member = self.db.query(AccountingUnitCombinationMember).filter(
            AccountingUnitCombinationMember.combination_id == combination_id,
            AccountingUnitCombinationMember.unit_id == unit_id
        ).first()
        
        if member:
            member.is_active = False
            self.db.commit()

    def get_combination_units(self, combination_id: int) -> List[AccountingUnit]:
        """获取组合包含的所有核算单位"""
        members = self.db.query(AccountingUnitCombinationMember).filter(
            AccountingUnitCombinationMember.combination_id == combination_id,
            AccountingUnitCombinationMember.is_active == True
        ).order_by(AccountingUnitCombinationMember.priority).all()
        
        unit_ids = [m.unit_id for m in members]
        return self.db.query(AccountingUnit).filter(AccountingUnit.id.in_(unit_ids)).all()

    def link_to_entity(self, unit_id: int, entity_id: int, relation_type: str = "primary") -> None:
        """关联核算单位到会计主体"""
        existing = self.db.query(AccountingUnitEntityRelation).filter(
            AccountingUnitEntityRelation.unit_id == unit_id,
            AccountingUnitEntityRelation.entity_id == entity_id
        ).first()
        
        if not existing:
            relation = AccountingUnitEntityRelation(
                unit_id=unit_id,
                entity_id=entity_id,
                relation_type=relation_type
            )
            self.db.add(relation)
            self.db.commit()

    def get_units_by_entity(self, entity_id: int) -> List[AccountingUnit]:
        """获取会计主体关联的核算单位"""
        relations = self.db.query(AccountingUnitEntityRelation).filter(
            AccountingUnitEntityRelation.entity_id == entity_id,
            AccountingUnitEntityRelation.is_active == True
        ).all()
        
        unit_ids = [r.unit_id for r in relations]
        return self.db.query(AccountingUnit).filter(AccountingUnit.id.in_(unit_ids)).all()

    def get_units_across_entities(self, entity_ids: List[int]) -> List[AccountingUnit]:
        """获取跨多个会计主体的核算单位"""
        relations = self.db.query(AccountingUnitEntityRelation).filter(
            AccountingUnitEntityRelation.entity_id.in_(entity_ids),
            AccountingUnitEntityRelation.is_active == True
        ).all()
        
        unit_ids = [r.unit_id for r in relations]
        units = self.db.query(AccountingUnit).filter(AccountingUnit.id.in_(unit_ids)).all()
        
        # 筛选出关联多个主体的单位
        cross_entity_units = []
        for unit in units:
            entity_count = self.db.query(AccountingUnitEntityRelation).filter(
                AccountingUnitEntityRelation.unit_id == unit.id,
                AccountingUnitEntityRelation.is_active == True
            ).count()
            if entity_count > 1:
                cross_entity_units.append(unit)
        
        return cross_entity_units

    def find_unit_by_name(self, unit_name: str) -> List[AccountingUnit]:
        """通过名称查找核算单位（支持模糊匹配）"""
        return self.search_units(unit_name)

    def search_units(self, keyword: str) -> List[AccountingUnit]:
        """按名称、描述和标签检索核算单位"""
        if not keyword:
            return self.get_units_by_type()

        pattern = f"%{keyword}%"
        tag_unit_ids = self.db.query(AccountingUnitTag.unit_id).filter(
            AccountingUnitTag.tag.ilike(pattern)
        )

        return self.db.query(AccountingUnit).filter(
            AccountingUnit.is_active == True,
            or_(
                AccountingUnit.unit_name.ilike(pattern),
                AccountingUnit.description.ilike(pattern),
                AccountingUnit.id.in_(tag_unit_ids),
            )
        ).all()

    def get_unit_hierarchy(self, unit_id: int) -> List[AccountingUnit]:
        """获取核算单位的层级链"""
        hierarchy = []
        current = self.db.query(AccountingUnit).filter(AccountingUnit.id == unit_id).first()
        
        while current:
            hierarchy.append(current)
            if current.parent_id:
                current = self.db.query(AccountingUnit).filter(AccountingUnit.id == current.parent_id).first()
            else:
                break
        
        return hierarchy

    def get_child_units(self, parent_id: int) -> List[AccountingUnit]:
        """获取子级核算单位"""
        return self.db.query(AccountingUnit).filter(
            AccountingUnit.parent_id == parent_id,
            AccountingUnit.is_active == True
        ).all()

    def record_version(self, unit_id: int, changes: Dict[str, Any], change_reason: Optional[str] = None) -> AccountingUnitVersion:
        """记录核算单位版本"""
        version_count = self.db.query(AccountingUnitVersion).filter(
            AccountingUnitVersion.unit_id == unit_id
        ).count()
        return self.create_version(
            unit_id=unit_id,
            version_name=f"版本 {version_count + 1}",
            effective_date=date.today(),
            changes=changes,
            change_reason=change_reason
        )

    def create_version(self, unit_id: int, version_name: str, effective_date: date,
                       changes: Dict[str, Any], change_reason: Optional[str] = None,
                       changed_by: str = "system") -> AccountingUnitVersion:
        """创建核算单位版本"""
        unit = self.db.query(AccountingUnit).filter(AccountingUnit.id == unit_id).first()
        if not unit:
            raise ValueError("Unit not found")

        version_count = self.db.query(AccountingUnitVersion).filter(
            AccountingUnitVersion.unit_id == unit_id
        ).count()

        version = AccountingUnitVersion(
            unit_id=unit_id,
            version_number=version_count + 1,
            version_name=version_name,
            effective_date=effective_date,
            changes=changes,
            change_reason=change_reason,
            changed_by=changed_by
        )

        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def get_versions(self, unit_id: int) -> List[AccountingUnitVersion]:
        """获取核算单位的版本历史"""
        return self.db.query(AccountingUnitVersion).filter(
            AccountingUnitVersion.unit_id == unit_id
        ).order_by(AccountingUnitVersion.version_number).all()

    def add_tag(self, unit_id: int, tag: str, tag_type: str = "name", confidence: float = 0.8) -> None:
        """添加核算单位标签"""
        existing = self.db.query(AccountingUnitTag).filter(
            AccountingUnitTag.unit_id == unit_id,
            AccountingUnitTag.tag == tag
        ).first()
        
        if not existing:
            unit_tag = AccountingUnitTag(
                unit_id=unit_id,
                tag=tag,
                tag_type=tag_type,
                confidence=confidence
            )
            self.db.add(unit_tag)
            self.db.commit()

    def get_units_by_type(self, type_code: Optional[str] = None) -> List[AccountingUnit]:
        """按类型筛选核算单位"""
        query = self.db.query(AccountingUnit).filter(AccountingUnit.is_active == True)
        
        if type_code:
            unit_type = self.db.query(AccountingUnitType).filter(
                AccountingUnitType.type_code == type_code
            ).first()
            if unit_type:
                query = query.filter(AccountingUnit.unit_type_id == unit_type.id)
        
        return query.all()

    def get_units_with_multiple_entities(self) -> List[Dict[str, Any]]:
        """获取跨多个会计主体的核算单位"""
        result = []
        
        units = self.db.query(AccountingUnit).filter(AccountingUnit.is_active == True).all()
        
        for unit in units:
            relations = self.db.query(AccountingUnitEntityRelation).filter(
                AccountingUnitEntityRelation.unit_id == unit.id,
                AccountingUnitEntityRelation.is_active == True
            ).all()
            
            if len(relations) > 1:
                entities = []
                for rel in relations:
                    entity = self.db.query(Entity).filter(Entity.id == rel.entity_id).first()
                    if entity:
                        entities.append({
                            "entity_id": entity.id,
                            "entity_name": entity.entity_name,
                            "relation_type": rel.relation_type
                        })
                
                result.append({
                    "unit_id": unit.id,
                    "unit_name": unit.unit_name,
                    "entities": entities,
                    "entity_count": len(entities)
                })
        
        return result

    def initialize_default_industries(self) -> List[Industry]:
        """初始化默认行业颗粒度推荐。"""
        default_industries = [
            {
                "industry_code": "manufacturing",
                "industry_name": "制造业",
                "industry_description": "生产制造企业，通常需要按物料、产品、项目、部门核算成本与收入。",
                "recommended_granularity": "material/product/project/department",
                "granularity_description": "建议关注物料、产品、项目、部门等成本归集维度。",
                "supported_unit_types": ["material", "product", "project", "department"],
            },
            {
                "industry_code": "trade",
                "industry_name": "贸易",
                "industry_description": "贸易批发和零售企业，通常需要按SKU、渠道、客户核算。",
                "recommended_granularity": "sku/channel/customer",
                "granularity_description": "建议关注SKU、渠道、客户等经营毛利维度。",
                "supported_unit_types": ["sku", "channel", "customer"],
            },
            {
                "industry_code": "service",
                "industry_name": "服务",
                "industry_description": "服务业企业，通常需要按项目、部门、客户核算。",
                "recommended_granularity": "project/department/customer",
                "granularity_description": "建议关注项目、部门、客户等服务交付维度。",
                "supported_unit_types": ["project", "department", "customer"],
            },
        ]

        industries = []
        for item in default_industries:
            industry = self.db.query(Industry).filter(
                Industry.industry_code == item["industry_code"]
            ).first()
            if not industry:
                industry = Industry(**item)
                self.db.add(industry)
            else:
                for key, value in item.items():
                    setattr(industry, key, value)
            industries.append(industry)

        self.db.commit()
        for industry in industries:
            self.db.refresh(industry)
        return industries

    def recommend_granularity(self, industry_code_or_name: str) -> Dict[str, Any]:
        """按行业编码或名称返回推荐核算颗粒度。"""
        builtin_rules = {
            "manufacturing": ["material", "product", "project", "department"],
            "制造业": ["material", "product", "project", "department"],
            "trade": ["sku", "channel", "customer"],
            "trading": ["sku", "channel", "customer"],
            "贸易": ["sku", "channel", "customer"],
            "service": ["project", "department", "customer"],
            "服务": ["project", "department", "customer"],
            "服务业": ["project", "department", "customer"],
        }
        industry = self.db.query(Industry).filter(
            or_(
                Industry.industry_code == industry_code_or_name,
                Industry.industry_name == industry_code_or_name,
            )
        ).first()

        if industry:
            granularities = industry.supported_unit_types or industry.recommended_granularity.split("/")
            return {
                "industry_id": industry.id,
                "industry_code": industry.industry_code,
                "industry_name": industry.industry_name,
                "recommended_granularity": industry.recommended_granularity,
                "granularities": granularities,
                "description": industry.granularity_description,
                "source": "database",
            }

        granularities = builtin_rules.get(industry_code_or_name, [])
        return {
            "industry_id": None,
            "industry_code": industry_code_or_name,
            "industry_name": industry_code_or_name,
            "recommended_granularity": "/".join(granularities),
            "granularities": granularities,
            "description": "内置行业推荐规则" if granularities else "未找到行业推荐规则",
            "source": "builtin",
        }

    def create_material(
        self,
        material_code: str,
        material_name: str,
        material_type: str,
        industry_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        unit: Optional[str] = None,
        specification: Optional[str] = None,
    ) -> Material:
        """创建物料。"""
        hierarchy_level = 1
        if parent_id:
            parent = self.db.query(Material).filter(Material.id == parent_id).first()
            if not parent:
                raise ValueError("Parent material not found")
            hierarchy_level = parent.hierarchy_level + 1

        material = Material(
            material_code=material_code,
            material_name=material_name,
            material_type=material_type,
            parent_id=parent_id,
            hierarchy_level=hierarchy_level,
            unit=unit,
            specification=specification,
        )
        self.db.add(material)
        self.db.commit()
        self.db.refresh(material)
        return material

    def create_bom(
        self,
        parent_material_id: int,
        child_material_id: int,
        quantity: float,
        loss_rate: Optional[float] = None,
    ) -> MaterialBOMItem:
        """创建一层BOM关系。"""
        parent = self.db.query(Material).filter(Material.id == parent_material_id).first()
        child = self.db.query(Material).filter(Material.id == child_material_id).first()
        if not parent or not child:
            raise ValueError("Material not found")

        bom = self.db.query(MaterialBOM).filter(
            MaterialBOM.finished_goods_id == parent_material_id,
            MaterialBOM.is_active == True,
        ).first()
        if not bom:
            bom = MaterialBOM(
                bom_code=f"BOM-{parent.material_code}",
                bom_name=f"{parent.material_name} BOM",
                finished_goods_id=parent_material_id,
            )
            self.db.add(bom)
            self.db.commit()
            self.db.refresh(bom)

        item = MaterialBOMItem(
            bom_id=bom.id,
            material_id=child_material_id,
            quantity=quantity,
            unit=child.unit or "",
            wastage_rate=loss_rate,
            sequence=self.db.query(MaterialBOMItem).filter(MaterialBOMItem.bom_id == bom.id).count() + 1,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_material_bom(self, material_id: int) -> Optional[Dict[str, Any]]:
        """查询物料一层BOM结构。"""
        material = self.db.query(Material).filter(Material.id == material_id).first()
        if not material:
            return None

        bom = self.db.query(MaterialBOM).filter(
            MaterialBOM.finished_goods_id == material_id,
            MaterialBOM.is_active == True,
        ).first()
        children = []
        if bom:
            items = self.db.query(MaterialBOMItem).filter(
                MaterialBOMItem.bom_id == bom.id
            ).order_by(MaterialBOMItem.sequence).all()
            for item in items:
                child = self.db.query(Material).filter(Material.id == item.material_id).first()
                children.append({
                    "bom_item_id": item.id,
                    "material_id": item.material_id,
                    "material_code": child.material_code if child else None,
                    "material_name": child.material_name if child else None,
                    "material_type": child.material_type if child else None,
                    "quantity": float(item.quantity),
                    "unit": item.unit,
                    "loss_rate": float(item.wastage_rate) if item.wastage_rate is not None else None,
                    "sequence": item.sequence,
                })

        return {
            "material_id": material.id,
            "material_code": material.material_code,
            "material_name": material.material_name,
            "bom_id": bom.id if bom else None,
            "children": children,
        }