from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.db.models import InternalControl, ControlTest, ControlAlert, Organization


class InternalControlService:
    def __init__(self, db: Session):
        self.db = db

    def get_control(self, control_id: int) -> Optional[InternalControl]:
        return self.db.query(InternalControl).filter(InternalControl.id == control_id).first()

    def get_controls_by_category(self, category: Optional[str] = None) -> List[InternalControl]:
        query = self.db.query(InternalControl)
        if category:
            query = query.filter(InternalControl.control_category == category)
        return query.all()

    def get_controls_by_industry(self, industry: str) -> List[InternalControl]:
        return self.db.query(InternalControl).filter(
            InternalControl.industries.contains([industry])
        ).all()

    def execute_control_test(self, organization_id: int, control_id: int, 
                             transaction_id: Optional[int] = None,
                             evidence_found: List[str] | None = None,
                             evidence_missing: List[str] | None = None) -> ControlTest:
        control = self.get_control(control_id)
        if not control:
            raise ValueError(f"Control {control_id} not found")
        
        evidence_found = evidence_found or []
        evidence_missing = evidence_missing or []
        
        is_executed = len(evidence_found) > 0
        execution_quality = self._calculate_execution_quality(control, evidence_found, evidence_missing)
        
        inherent_risk = self._convert_risk_to_float(control.inherent_risk)
        control_risk = self._calculate_control_risk(execution_quality)
        detection_risk = 0.5
        overall_risk = inherent_risk * control_risk * detection_risk
        
        alert_level, alert_message = self._determine_alert(overall_risk, evidence_missing)
        
        test = ControlTest(
            organization_id=organization_id,
            control_id=control_id,
            transaction_id=transaction_id,
            is_executed=is_executed,
            evidence_found=evidence_found,
            evidence_missing=evidence_missing,
            execution_quality=execution_quality,
            inherent_risk=inherent_risk,
            control_risk=control_risk,
            detection_risk=detection_risk,
            overall_risk=overall_risk,
            alert_level=alert_level,
            alert_message=alert_message,
            suggested_procedure=self._generate_suggested_procedure(alert_level, control)
        )
        
        self.db.add(test)
        self.db.commit()
        self.db.refresh(test)
        
        if alert_level in ["critical", "high"]:
            self._create_control_alert(organization_id, control_id, test.id, alert_level, 
                                       evidence_missing, control_risk, detection_risk)
        
        return test

    def _calculate_execution_quality(self, control: InternalControl, 
                                     found: List[str], missing: List[str]) -> str:
        required = control.evidence_required
        if not required:
            return "full"
        
        required_count = len(required)
        found_count = len([e for e in found if e in required])
        
        if found_count == required_count:
            return "full"
        elif found_count > 0:
            return "partial"
        else:
            return "none"

    def _convert_risk_to_float(self, risk_level: str) -> float:
        risk_map = {"high": 0.8, "medium": 0.5, "low": 0.2}
        return risk_map.get(risk_level, 0.5)

    def _calculate_control_risk(self, execution_quality: str) -> float:
        quality_map = {"full": 0.2, "partial": 0.5, "none": 0.8}
        return quality_map.get(execution_quality, 0.5)

    def _determine_alert(self, overall_risk: float, missing: List[str]) -> tuple[str, str]:
        if overall_risk > 0.32:
            return ("critical", f"高风险: 内部控制测试未通过，缺失证据: {', '.join(missing)}")
        elif overall_risk > 0.2:
            return ("high", f"中等风险: 内部控制执行不充分")
        elif overall_risk > 0.1:
            return ("medium", f"低风险: 内部控制部分有效")
        else:
            return ("low", "内部控制测试通过")

    def _generate_suggested_procedure(self, alert_level: str, control: InternalControl) -> str:
        procedures = {
            "critical": f"立即执行实质性测试，扩大样本量，重点检查与'{control.control_name}'相关的所有交易",
            "high": f"增加实质性程序范围，对'{control.control_name}'相关交易进行详细测试",
            "medium": f"执行额外的控制测试，确认控制有效性",
            "low": f"控制测试通过，可减少实质性程序"
        }
        return procedures.get(alert_level, "根据风险评估结果执行适当审计程序")

    def _create_control_alert(self, organization_id: int, control_id: int, 
                              test_id: int, alert_level: str, evidence_missing: List[str],
                              control_risk: float = 0.8, detection_risk: float = 0.5) -> None:
        control = self.get_control(control_id)
        if not control:
            return
        
        inherent_risk = self._convert_risk_to_float(control.inherent_risk)
        overall_risk = inherent_risk * control_risk * detection_risk
        
        alert = ControlAlert(
            organization_id=organization_id,
            control_id=control_id,
            test_id=test_id,
            alert_level=alert_level,
            business_type=control.control_category,
            evidence_involved=evidence_missing,
            problem_type="missing_evidence" if evidence_missing else "incomplete_evidence",
            description=f"内部控制'{control.control_name}'测试发现异常",
            inherent_risk=inherent_risk,
            control_risk=control_risk,
            detection_risk=detection_risk,
            overall_risk=overall_risk,
            suggested_procedure=self._generate_suggested_procedure(alert_level, control),
            priority=1 if alert_level == "critical" else 2
        )
        
        self.db.add(alert)
        self.db.commit()

    def get_alerts_by_organization(self, organization_id: int, 
                                   alert_level: Optional[str] = None) -> List[ControlAlert]:
        query = self.db.query(ControlAlert).filter(ControlAlert.organization_id == organization_id)
        if alert_level:
            query = query.filter(ControlAlert.alert_level == alert_level)
        return query.order_by(ControlAlert.priority, ControlAlert.created_at).all()

    def acknowledge_alert(self, alert_id: int) -> bool:
        alert = self.db.query(ControlAlert).filter(ControlAlert.id == alert_id).first()
        if alert:
            alert.priority = 0
            self.db.commit()
            return True
        return False

    def initialize_default_controls(self) -> None:
        default_controls = [
            {
                "control_code": "PC-001",
                "control_name": "采购申请审批控制",
                "control_type": "preventive",
                "control_category": "approval",
                "description": "采购申请需经部门负责人审批",
                "objective": "确保采购申请合理、必要",
                "trigger_conditions": ["采购金额>1000"],
                "evidence_required": ["采购申请表", "审批记录"],
                "frequency": "per_transaction",
                "industries": ["制造业", "贸易", "服务"],
                "company_size": "all",
                "risk_category": "采购风险",
                "inherent_risk": "medium",
                "control_risk": "low"
            },
            {
                "control_code": "PC-002",
                "control_name": "供应商选择控制",
                "control_type": "preventive",
                "control_category": "authorization",
                "description": "新供应商需经采购部门审批",
                "objective": "确保供应商资质合规",
                "trigger_conditions": ["新增供应商"],
                "evidence_required": ["供应商评估表", "营业执照", "审批记录"],
                "frequency": "per_transaction",
                "industries": ["制造业", "贸易", "服务"],
                "company_size": "all",
                "risk_category": "采购风险",
                "inherent_risk": "high",
                "control_risk": "low"
            },
            {
                "control_code": "PC-003",
                "control_name": "收货验收控制",
                "control_type": "detective",
                "control_category": "approval",
                "description": "入库需经质量验收",
                "objective": "确保收到货物符合要求",
                "trigger_conditions": ["采购入库"],
                "evidence_required": ["入库单", "验收报告"],
                "frequency": "per_transaction",
                "industries": ["制造业", "贸易"],
                "company_size": "all",
                "risk_category": "存货风险",
                "inherent_risk": "medium",
                "control_risk": "low"
            },
            {
                "control_code": "SC-001",
                "control_name": "销售订单审批控制",
                "control_type": "preventive",
                "control_category": "approval",
                "description": "大额销售订单需经审批",
                "objective": "确保销售订单合理",
                "trigger_conditions": ["订单金额>10000"],
                "evidence_required": ["销售订单", "审批记录"],
                "frequency": "per_transaction",
                "industries": ["制造业", "贸易", "服务"],
                "company_size": "all",
                "risk_category": "销售风险",
                "inherent_risk": "medium",
                "control_risk": "low"
            },
            {
                "control_code": "SC-002",
                "control_name": "发货控制",
                "control_type": "detective",
                "control_category": "approval",
                "description": "发货需有完整的销售订单",
                "objective": "确保发货与订单一致",
                "trigger_conditions": ["销售发货"],
                "evidence_required": ["销售订单", "发货单"],
                "frequency": "per_transaction",
                "industries": ["制造业", "贸易"],
                "company_size": "all",
                "risk_category": "销售风险",
                "inherent_risk": "medium",
                "control_risk": "low"
            },
            {
                "control_code": "TC-001",
                "control_name": "银行余额调节",
                "control_type": "detective",
                "control_category": "reconciliation",
                "description": "每月进行银行对账",
                "objective": "确保银行存款记录准确",
                "trigger_conditions": ["月末"],
                "evidence_required": ["银行对账单", "余额调节表"],
                "frequency": "monthly",
                "industries": ["all"],
                "company_size": "all",
                "risk_category": "货币资金风险",
                "inherent_risk": "high",
                "control_risk": "low"
            },
            {
                "control_code": "TC-002",
                "control_name": "现金盘点",
                "control_type": "detective",
                "control_category": "reconciliation",
                "description": "定期进行现金盘点",
                "objective": "确保现金安全",
                "trigger_conditions": ["每周"],
                "evidence_required": ["盘点表", "监盘记录"],
                "frequency": "weekly",
                "industries": ["all"],
                "company_size": "all",
                "risk_category": "货币资金风险",
                "inherent_risk": "high",
                "control_risk": "low"
            },
            {
                "control_code": "TC-003",
                "control_name": "大额支付审批",
                "control_type": "preventive",
                "control_category": "approval",
                "description": "大额支付需多级审批",
                "objective": "确保资金支付安全",
                "trigger_conditions": ["支付金额>50000"],
                "evidence_required": ["付款申请单", "审批记录"],
                "frequency": "per_transaction",
                "industries": ["all"],
                "company_size": "all",
                "risk_category": "货币资金风险",
                "inherent_risk": "high",
                "control_risk": "low"
            }
        ]
        
        for ctrl_data in default_controls:
            existing = self.db.query(InternalControl).filter(
                InternalControl.control_code == ctrl_data["control_code"]
            ).first()
            if not existing:
                control = InternalControl(**ctrl_data)
                self.db.add(control)
        
        self.db.commit()

    def calculate_risk_matrix(self, organization_id: int) -> Dict[str, Any]:
        tests = self.db.query(ControlTest).filter(
            ControlTest.organization_id == organization_id
        ).all()
        
        if not tests:
            return {"overall_risk": 0.5, "risk_level": "medium", "details": []}
        
        avg_inherent = sum(t.inherent_risk for t in tests) / len(tests)
        avg_control = sum(t.control_risk for t in tests) / len(tests)
        avg_detection = sum(t.detection_risk for t in tests) / len(tests)
        overall_risk = avg_inherent * avg_control * avg_detection
        
        risk_level = "critical" if overall_risk > 0.32 else \
                     "high" if overall_risk > 0.2 else \
                     "medium" if overall_risk > 0.1 else "low"
        
        return {
            "overall_risk": overall_risk,
            "risk_level": risk_level,
            "risk_matrix": {
                "inherent_risk": avg_inherent,
                "control_risk": avg_control,
                "detection_risk": avg_detection
            },
            "details": [
                {
                    "control_id": t.control_id,
                    "overall_risk": t.overall_risk,
                    "alert_level": t.alert_level
                } for t in tests
            ]
        }