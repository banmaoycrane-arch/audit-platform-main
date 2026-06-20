from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import BusinessCycle, CycleStep, CycleBreak, Organization


class BusinessCycleService:
    def __init__(self, db: Session):
        self.db = db

    def create_cycle(self, organization_id: int, cycle_type: str, cycle_name: str, 
                    start_date: Optional[date] = None) -> BusinessCycle:
        cycle = BusinessCycle(
            organization_id=organization_id,
            cycle_type=cycle_type,
            cycle_name=cycle_name,
            start_date=start_date,
            status="in_progress"
        )
        self.db.add(cycle)
        self.db.commit()
        self.db.refresh(cycle)
        return cycle

    def get_cycle(self, cycle_id: int) -> Optional[BusinessCycle]:
        return self.db.query(BusinessCycle).filter(BusinessCycle.id == cycle_id).first()

    def get_cycles_by_organization(self, organization_id: int, 
                                   cycle_type: Optional[str] = None) -> List[BusinessCycle]:
        query = self.db.query(BusinessCycle).filter(BusinessCycle.organization_id == organization_id)
        if cycle_type:
            query = query.filter(BusinessCycle.cycle_type == cycle_type)
        return query.all()

    def update_cycle_status(self, cycle_id: int, status: str) -> Optional[BusinessCycle]:
        cycle = self.get_cycle(cycle_id)
        if cycle:
            cycle.status = status
            if status == "completed":
                cycle.end_date = date.today()
            self.db.commit()
            self.db.refresh(cycle)
        return cycle

    def calculate_completeness(self, cycle_id: int) -> float:
        steps = self.db.query(CycleStep).filter(CycleStep.cycle_id == cycle_id).all()
        if not steps:
            return 0.0
        completed_count = sum(1 for step in steps if step.status == "completed")
        return completed_count / len(steps)

    def add_step(self, cycle_id: int, step_order: int, step_type: str, 
                 step_name: str) -> CycleStep:
        step = CycleStep(
            cycle_id=cycle_id,
            step_order=step_order,
            step_type=step_type,
            step_name=step_name
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def update_step(self, step_id: int, **kwargs) -> Optional[CycleStep]:
        step = self.db.query(CycleStep).filter(CycleStep.id == step_id).first()
        if step:
            for key, value in kwargs.items():
                setattr(step, key, value)
            self.db.commit()
            self.db.refresh(step)
        return step

    def add_cycle_break(self, cycle_id: int, break_point: int, break_type: str, 
                        severity: str, description: str, suggestion: str, 
                        audit_procedure: str) -> CycleBreak:
        cycle_break = CycleBreak(
            cycle_id=cycle_id,
            break_point=break_point,
            break_type=break_type,
            severity=severity,
            description=description,
            suggestion=suggestion,
            audit_procedure=audit_procedure
        )
        self.db.add(cycle_break)
        self.db.commit()
        self.db.refresh(cycle_break)
        
        cycle = self.get_cycle(cycle_id)
        if cycle:
            cycle.status = "broken"
            self.db.commit()
        
        return cycle_break

    def analyze_cycle_break(self, cycle_id: int) -> List[Dict[str, Any]]:
        cycle = self.get_cycle(cycle_id)
        if not cycle:
            return []
        
        steps = self.db.query(CycleStep).filter(CycleStep.cycle_id == cycle_id)\
                      .order_by(CycleStep.step_order).all()
        
        breaks = []
        for i, step in enumerate(steps):
            if step.status == "missing":
                breaks.append({
                    "step_order": step.step_order,
                    "step_name": step.step_name,
                    "step_type": step.step_type,
                    "break_type": "evidence_break",
                    "severity": "high" if i < len(steps) - 1 else "medium",
                    "description": f"缺少步骤 '{step.step_name}' 的证据",
                    "suggestion": "请补充相关证据文件",
                    "audit_procedure": "检查缺失证据对业务循环完整性的影响"
                })
            elif step.status == "completed" and step.actual_date:
                if i > 0:
                    prev_step = steps[i - 1]
                    if prev_step.actual_date and step.actual_date < prev_step.actual_date:
                        breaks.append({
                            "step_order": step.step_order,
                            "step_name": step.step_name,
                            "step_type": step.step_type,
                            "break_type": "date_error",
                            "severity": "high",
                            "description": f"步骤 '{step.step_name}' 的日期早于前一步骤",
                            "suggestion": "核实日期准确性",
                            "audit_procedure": "检查日期逻辑是否正确"
                        })
        
        return breaks

    def get_risk_extension(self, cycle_id: int) -> Dict[str, Any]:
        cycle = self.get_cycle(cycle_id)
        if not cycle or cycle.status != "completed":
            return {}
        
        if cycle.cycle_type == "purchase":
            return {
                "next_cycle": "payment",
                "next_cycle_description": "采购循环完成后应触发付款循环",
                "risk_factors": [
                    "检查是否存在长期未付款项",
                    "核实应付账款账龄是否合理",
                    "确认是否存在未入账的负债"
                ]
            }
        elif cycle.cycle_type == "sales":
            return {
                "next_cycle": "collection",
                "next_cycle_description": "销售循环完成后应触发收款循环",
                "risk_factors": [
                    "检查应收账款是否逾期",
                    "核实坏账准备计提是否充分",
                    "确认收入确认时点是否正确"
                ]
            }
        elif cycle.cycle_type == "production":
            return {
                "next_cycle": "cost_allocation",
                "next_cycle_description": "生产循环完成后应触发成本分配循环",
                "risk_factors": [
                    "检查生产成本归集是否完整",
                    "核实制造费用分摊是否合理",
                    "确认在产品计价是否准确"
                ]
            }
        
        return {}

    def delete_cycle(self, cycle_id: int) -> bool:
        cycle = self.get_cycle(cycle_id)
        if cycle:
            self.db.delete(cycle)
            self.db.commit()
            return True
        return False