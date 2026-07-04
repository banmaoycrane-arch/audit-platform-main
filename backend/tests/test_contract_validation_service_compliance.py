# -*- coding: utf-8 -*-
"""合同校验服务 - 采购合同合规性评分单元测试"""

from decimal import Decimal

import pytest

from app.services.basic_data.contract_parser_service import (
    CommodityItem,
    ComplianceAssessment,
    ContractParseResult,
    ContractParty,
    ContractPenalty,
    ContractPeriod,
    ContractPrice,
    FinancialTerms,
    TaxLiabilityClause,
    TaxTreatment,
)
from app.services.basic_data.contract_validation_service import (
    ComplianceDimension,
    ContractValidationService,
    ProcurementComplianceReport,
)


@pytest.fixture
def validation_service():
    return ContractValidationService()


@pytest.fixture
def complete_procurement_result():
    """完整合规的采购合同解析结果"""
    result = ContractParseResult(
        contract_type="采购",
        contract_valid=True,
        commercial_substance=True,
        collection_probable=True,
        signing_date="2026-06-01",
        period=ContractPeriod(start_date="2026-06-01", end_date="2027-05-31"),
        price=ContractPrice(
            total_amount=Decimal("113000"),
            tax_rate=Decimal("0.13"),
            payment_terms="预付30%，到货70%",
        ),
        parties=[
            ContractParty(name="甲方科技", role="甲方", tax_id="9111", address="北京"),
            ContractParty(name="乙方供应", role="乙方", tax_id="9112", address="上海"),
        ],
        commodities=[
            CommodityItem(
                item_no=1,
                product_name="服务器",
                specification="2U",
                model_number="DL380",
                unit="台",
                quantity=Decimal("10"),
                unit_price=Decimal("10000"),
                total_price=Decimal("100000"),
                quality_standard="国标",
                delivery_terms="送货上门",
                warranty_period="3年",
            )
        ],
        financial_terms=FinancialTerms(
            contract_amount=Decimal("113000"),
            goods_amount=Decimal("100000"),
            transportation_fee=Decimal("3000"),
            warehousing_cost=Decimal("0.00"),
            insurance_fee=Decimal("0.00"),
            tax_rate=Decimal("0.13"),
            explicitly_stated=[
                "goods_amount",
                "transportation_fee",
                "warehousing_cost",
                "insurance_fee",
            ],
        ),
        tax_liability=TaxLiabilityClause(
            is_critical=True,
            responsible_party="乙方",
            tax_type="增值税",
            tax_rate=Decimal("0.13"),
            invoice_type="增值税专用发票",
            full_text="付款前开票",
        ),
        tax_treatment=TaxTreatment(tax_rate=Decimal("0.13")),
        penalties=[ContractPenalty(penalty_clause="迟延交货违约金")],
        compliance_assessment=ComplianceAssessment(score=90, risk_level="low"),
    )
    return result


def test_assess_procurement_compliance_high_score(
    validation_service, complete_procurement_result
):
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=95
    )

    assert isinstance(report, ProcurementComplianceReport)
    assert report.overall_score == 98  # round((95 + 100) / 2)
    assert report.risk_level == "low"
    assert report.compliance_score >= 95
    assert len(report.dimensions) == 6
    assert not report.risk_flags


def test_assess_missing_parties(validation_service, complete_procurement_result):
    complete_procurement_result.parties = []
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    party_dim = next(d for d in report.dimensions if d.name == "主体完整性")
    assert party_dim.score == 50
    assert "未识别到合同主体" in party_dim.findings
    assert report.risk_level in ("medium", "high")


def test_assess_single_party(validation_service, complete_procurement_result):
    complete_procurement_result.parties = [
        ContractParty(name="甲方", role="甲方")
    ]
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    party_dim = next(d for d in report.dimensions if d.name == "主体完整性")
    assert "合同主体不足两方" in party_dim.findings


def test_assess_party_missing_tax_id(validation_service, complete_procurement_result):
    complete_procurement_result.parties[0].tax_id = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    party_dim = next(d for d in report.dimensions if d.name == "主体完整性")
    assert any("纳税人识别号" in f for f in party_dim.findings)


def test_assess_procurement_missing_commodities(
    validation_service, complete_procurement_result
):
    complete_procurement_result.commodities = []
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    commodity_dim = next(d for d in report.dimensions if d.name == "标的明确性")
    assert "采购合同未识别商品明细" in commodity_dim.findings
    assert commodity_dim.score == 60


def test_assess_device_missing_model(validation_service, complete_procurement_result):
    complete_procurement_result.commodities[0].product_name = "服务器设备"
    complete_procurement_result.commodities[0].model_number = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    commodity_dim = next(d for d in report.dimensions if d.name == "标的明确性")
    assert any("设备类商品" in f for f in commodity_dim.findings)


def test_assess_commodity_quantity_zero(validation_service, complete_procurement_result):
    complete_procurement_result.commodities[0].quantity = Decimal("0")
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    commodity_dim = next(d for d in report.dimensions if d.name == "标的明确性")
    assert any("数量异常" in f for f in commodity_dim.findings)


def test_assess_price_missing_total(validation_service, complete_procurement_result):
    complete_procurement_result.price.total_amount = Decimal("0")
    complete_procurement_result.financial_terms.contract_amount = Decimal("0")
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    price_dim = next(d for d in report.dimensions if d.name == "价格与支付")
    assert "合同总价未明确" in price_dim.findings


def test_assess_price_missing_payment_terms(
    validation_service, complete_procurement_result
):
    complete_procurement_result.price.payment_terms = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    price_dim = next(d for d in report.dimensions if d.name == "价格与支付")
    assert "缺少付款条件" in price_dim.findings


def test_assess_delivery_missing_period(validation_service, complete_procurement_result):
    complete_procurement_result.period = ContractPeriod()
    complete_procurement_result.commodities[0].delivery_terms = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    delivery_dim = next(d for d in report.dimensions if d.name == "交付与验收")
    assert "缺少合同履行期限" in delivery_dim.findings
    assert "缺少交货地点/方式条款" in delivery_dim.findings


def test_assess_tax_liability_missing(validation_service, complete_procurement_result):
    complete_procurement_result.tax_liability = TaxLiabilityClause()
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    tax_dim = next(d for d in report.dimensions if d.name == "税务责任")
    assert "缺少税务责任专项条款" in tax_dim.findings


def test_assess_tax_liability_critical_no_invoice_type(
    validation_service, complete_procurement_result
):
    complete_procurement_result.tax_liability.invoice_type = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    tax_dim = next(d for d in report.dimensions if d.name == "税务责任")
    assert "税务责任条款约定税率但未明确发票类型" in tax_dim.findings


def test_assess_tax_rate_inconsistent(validation_service, complete_procurement_result):
    complete_procurement_result.tax_liability.tax_rate = Decimal("0.06")
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    tax_dim = next(d for d in report.dimensions if d.name == "税务责任")
    assert "税务责任条款税率与税务处理税率不一致" in tax_dim.findings
    assert any("税务责任税率" in f for f in report.risk_flags)


def test_assess_penalty_missing(validation_service, complete_procurement_result):
    complete_procurement_result.penalties = []
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    penalty_dim = next(d for d in report.dimensions if d.name == "违约与争议")
    assert "缺少违约责任条款" in penalty_dim.findings


def test_assess_warranty_missing(validation_service, complete_procurement_result):
    complete_procurement_result.commodities[0].warranty_period = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    penalty_dim = next(d for d in report.dimensions if d.name == "违约与争议")
    assert "采购合同缺少质保期条款" in penalty_dim.findings


def test_assess_commodity_risk_flags(validation_service, complete_procurement_result):
    complete_procurement_result.commodities[0].missing_attributes = ["weight"]
    complete_procurement_result.commodities[0].consistency_errors = ["金额不一致"]
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    assert any("缺失属性" in f for f in report.risk_flags)
    assert any("一致性错误" in f for f in report.risk_flags)
    # 存在风险标记时，即使 compliance_score 高，risk_level 也应为 medium
    assert report.risk_level == "medium"


def test_assess_high_risk_level(validation_service, complete_procurement_result):
    # 制造多个严重缺失，确保合规得分低于 60
    complete_procurement_result.parties = []
    complete_procurement_result.commodities = []
    complete_procurement_result.price.total_amount = Decimal("0")
    complete_procurement_result.price.payment_terms = ""
    complete_procurement_result.period = ContractPeriod()
    complete_procurement_result.tax_liability = TaxLiabilityClause()
    complete_procurement_result.penalties = []
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=40
    )
    assert report.risk_level == "high"
    assert report.overall_score < 60
    assert "建议退回业务部门补充合同条款" in report.recommendations


def test_assess_medium_risk_level(validation_service, complete_procurement_result):
    complete_procurement_result.penalties = []
    complete_procurement_result.commodities[0].warranty_period = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=80
    )
    assert report.risk_level in ("medium", "low")


def test_assess_internal_control_notes(validation_service, complete_procurement_result):
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=95
    )
    assert "合规性良好" in report.internal_control_notes


def test_assess_internal_control_notes_high_risk(
    validation_service, complete_procurement_result
):
    complete_procurement_result.parties = []
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=40
    )
    assert "合规性较差" in report.internal_control_notes


def test_assess_weighted_score_calculation(validation_service):
    """测试加权得分计算"""
    result = ContractParseResult(
        contract_type="采购",
        price=ContractPrice(total_amount=Decimal("10000"), tax_rate=Decimal("0.13")),
        parties=[
            ContractParty(name="甲方", role="甲方", tax_id="1", address="北京"),
            ContractParty(name="乙方", role="乙方", tax_id="2", address="上海"),
        ],
        commodities=[
            CommodityItem(
                product_name="货物",
                specification="规格",
                model_number="M1",
                quantity=Decimal("1"),
                unit_price=Decimal("10000"),
                total_price=Decimal("10000"),
                quality_standard="国标",
                delivery_terms="送货",
                warranty_period="1年",
            )
        ],
        financial_terms=FinancialTerms(
            contract_amount=Decimal("10000"),
            explicitly_stated=["contract_amount"],
        ),
        tax_liability=TaxLiabilityClause(
            is_critical=True,
            responsible_party="乙方",
            tax_rate=Decimal("0.13"),
            invoice_type="专票",
        ),
        tax_treatment=TaxTreatment(tax_rate=Decimal("0.13")),
        penalties=[ContractPenalty(penalty_clause="违约")],
    )
    report = validation_service.assess_procurement_compliance(result, extraction_score=100)
    assert 0 <= report.compliance_score <= 100
    assert 0 <= report.overall_score <= 100


def test_compliance_dimension_dataclass():
    dim = ComplianceDimension(name="测试", weight=10, score=80, findings=["问题"])
    assert dim.name == "测试"
    assert dim.weight == 10


def test_procurement_compliance_report_dataclass():
    report = ProcurementComplianceReport(
        overall_score=70,
        risk_level="medium",
        missing_clauses=["缺少A"],
        recommendations=["补充A"],
    )
    assert report.overall_score == 70
    assert report.recommendations == ["补充A"]


def test_assess_party_missing_address(validation_service, complete_procurement_result):
    complete_procurement_result.parties[0].address = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    party_dim = next(d for d in report.dimensions if d.name == "主体完整性")
    assert any("地址" in f for f in party_dim.findings)


def test_assess_commodity_missing_specification(
    validation_service, complete_procurement_result
):
    complete_procurement_result.commodities[0].specification = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    commodity_dim = next(d for d in report.dimensions if d.name == "标的明确性")
    assert any("规格参数" in f for f in commodity_dim.findings)


def test_assess_commodity_non_device_missing_model(
    validation_service, complete_procurement_result
):
    complete_procurement_result.commodities[0].product_name = "原材料"
    complete_procurement_result.commodities[0].model_number = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    commodity_dim = next(d for d in report.dimensions if d.name == "标的明确性")
    # 非设备类商品缺少型号扣分较轻，不生成 findings
    assert commodity_dim.score >= 95


def test_assess_commodity_unit_price_zero(
    validation_service, complete_procurement_result
):
    complete_procurement_result.commodities[0].unit_price = Decimal("0")
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    commodity_dim = next(d for d in report.dimensions if d.name == "标的明确性")
    assert any("单价异常" in f for f in commodity_dim.findings)


def test_assess_commodity_missing_quality_standard(
    validation_service, complete_procurement_result
):
    complete_procurement_result.commodities[0].quality_standard = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    commodity_dim = next(d for d in report.dimensions if d.name == "标的明确性")
    assert any("质量标准" in f for f in commodity_dim.findings)


def test_assess_price_tax_rate_missing(validation_service, complete_procurement_result):
    complete_procurement_result.price.tax_rate = Decimal("0")
    complete_procurement_result.financial_terms.tax_rate = None
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    price_dim = next(d for d in report.dimensions if d.name == "价格与支付")
    assert "税率未明确" in price_dim.findings


def test_assess_price_unstated_material_fees(
    validation_service, complete_procurement_result
):
    complete_procurement_result.financial_terms.warehousing_cost = None
    complete_procurement_result.financial_terms.insurance_fee = None
    complete_procurement_result.financial_terms.explicitly_stated = [
        "goods_amount",
        "transportation_fee",
    ]
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    price_dim = next(d for d in report.dimensions if d.name == "价格与支付")
    assert any("warehousing_cost未明确且可能重大" in f for f in price_dim.findings)
    assert any("insurance_fee未明确且可能重大" in f for f in price_dim.findings)


def test_assess_tax_liability_missing_responsible_party(
    validation_service, complete_procurement_result
):
    complete_procurement_result.tax_liability.responsible_party = ""
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    tax_dim = next(d for d in report.dimensions if d.name == "税务责任")
    assert "重大税务责任条款未明确责任方" in tax_dim.findings
    assert "重大税务责任条款存在缺陷" in report.risk_flags


def test_assess_penalty_clause_text_missing(
    validation_service, complete_procurement_result
):
    complete_procurement_result.penalties = [ContractPenalty(penalty_clause="")]
    report = validation_service.assess_procurement_compliance(
        complete_procurement_result, extraction_score=90
    )
    penalty_dim = next(d for d in report.dimensions if d.name == "违约与争议")
    assert "违约责任条款原文缺失" in penalty_dim.findings
