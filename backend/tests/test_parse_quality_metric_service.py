# -*- coding: utf-8 -*-
"""
模块功能：解析质量指标服务单元测试
业务场景：验证解析质量指标记录、按日汇总、看板查询逻辑。
创建日期：2026-07-03
"""
from datetime import date

import pytest

from app.db.session import SessionLocal
from app.models.parse_quality_metric import ParseQualityMetric, ParseQualitySummary
from app.services.doc_parsing.parser_engine.parse_quality_metric_service import (
    get_quality_dashboard,
    record_parse_quality_metric,
)


@pytest.fixture
def db():
    """提供测试数据库会话，并在测试结束后回滚。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _clear_metrics(db_session):
    """清理测试产生的质量指标记录。"""
    db_session.query(ParseQualityMetric).delete()
    db_session.query(ParseQualitySummary).delete()
    db_session.commit()


def test_record_parse_quality_metric_creates_summary(db):
    """测试记录单次解析质量指标并生成每日汇总。"""
    _clear_metrics(db)

    report = {
        "consistency_rate": 0.95,
        "stability_score": 0.94,
        "review_required": True,
        "consistent_fields": [{"field": "contract_no", "normalized_field": "contract_no", "value": "C001"}],
        "conflict_fields": [{"field": "contract_amount", "normalized_field": "contract_amount", "rule_value": "100", "llm_value": "200"}],
        "rule_only_fields": [],
        "llm_only_fields": [],
    }

    metric = record_parse_quality_metric(
        db=db,
        file_name="test_contract.pdf",
        document_type="contract",
        comparison_report=report,
        correction_applied_count=1,
    )

    assert metric.document_type == "contract"
    assert metric.consistency_rate == 95.0
    assert metric.stability_score == 94.0
    assert metric.review_required == 1
    assert metric.conflict_count == 1
    assert metric.correction_applied_count == 1

    db.expire_all()
    summary_date = metric.created_at.date().isoformat() if metric.created_at else date.today().isoformat()
    summary = db.query(ParseQualitySummary).filter_by(
        summary_date=summary_date, document_type="contract"
    ).first()
    assert summary is not None
    assert summary.parse_count == 1
    assert summary.review_required_count == 1
    assert summary.correction_applied_total == 1


def test_get_quality_dashboard_returns_weighted_metrics(db):
    """测试看板接口返回加权聚合指标。"""
    _clear_metrics(db)

    report_high = {
        "consistency_rate": 1.0,
        "stability_score": 1.0,
        "review_required": False,
        "consistent_fields": [{"field": "contract_no", "normalized_field": "contract_no", "value": "C001"}],
        "conflict_fields": [],
        "rule_only_fields": [],
        "llm_only_fields": [],
    }
    report_low = {
        "consistency_rate": 0.90,
        "stability_score": 0.88,
        "review_required": True,
        "consistent_fields": [],
        "conflict_fields": [{"field": "amount", "normalized_field": "amount", "rule_value": "100", "llm_value": "200"}],
        "rule_only_fields": [],
        "llm_only_fields": [],
    }

    record_parse_quality_metric(db, "f1.pdf", "contract", report_high)
    record_parse_quality_metric(db, "f2.pdf", "contract", report_high)
    record_parse_quality_metric(db, "f3.pdf", "contract", report_low)

    db.expire_all()
    dashboard = get_quality_dashboard(db)

    assert dashboard["total_parse_count"] == 3
    assert dashboard["total_review_required_count"] == 1
    assert dashboard["overall_consistency_rate"] == pytest.approx(96.67, 0.01)
    assert dashboard["overall_stability_score"] == pytest.approx(96.0, 0.01)
    assert len(dashboard["trend"]) == 1
