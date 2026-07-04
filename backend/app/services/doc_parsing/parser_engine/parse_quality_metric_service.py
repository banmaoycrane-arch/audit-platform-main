# -*- coding: utf-8 -*-
"""
模块功能：解析质量指标记录与汇总服务
业务场景：在每次文件解析完成后记录质量指标，并支持按时间/文档类型聚合
        生成解析稳定性看板数据。
政策依据：审计可追溯要求、持续质量改进闭环管理。
输入数据：双引擎对比报告、解析结果、修正规则应用数。
输出结果：持久化的 ParseQualityMetric 记录和 ParseQualitySummary 汇总。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建，实现单次指标记录与按日汇总。
"""
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.parse_quality_metric import ParseQualityMetric, ParseQualitySummary
from app.services.doc_parsing.parser_engine.parser_engine_analyzer import EngineComparisonReport


def record_parse_quality_metric(
    db: Session,
    file_name: str,
    document_type: str,
    comparison_report: EngineComparisonReport | dict[str, Any] | None,
    source_file_id: int | None = None,
    rule_engine_used: bool = True,
    llm_engine_used: bool = True,
    correction_applied_count: int = 0,
) -> ParseQualityMetric:
    """
    记录一次文件解析的质量指标。

    业务逻辑：
        1. 从双引擎对比报告中提取一致性率、稳定性评分、冲突数、复核标志等。
        2. 计算字段级准确率与完整率。
        3. 持久化到 ParseQualityMetric。

    Args:
        db: 数据库会话。
        file_name: 原始文件名。
        document_type: 文档类型。
        comparison_report: 双引擎对比报告对象或其字典形式。
        source_file_id: 关联源文件ID（可选）。
        rule_engine_used: 是否使用了规则引擎。
        llm_engine_used: 是否使用了LLM引擎。
        correction_applied_count: 本次解析应用的修正规则数。

    Returns:
        ParseQualityMetric: 创建的质量指标记录。
    """
    report_dict: dict[str, Any] = {}
    if isinstance(comparison_report, dict):
        report_dict = comparison_report
    elif comparison_report is not None:
        report_dict = _comparison_report_to_dict(comparison_report)

    consistency_rate = float(report_dict.get("consistency_rate", 0.0) or 0.0)
    stability_score = float(report_dict.get("stability_score", 0.0) or 0.0)
    review_required = bool(report_dict.get("review_required", False))

    consistent_fields = report_dict.get("consistent_fields", [])
    conflict_fields = report_dict.get("conflict_fields", [])
    rule_only_fields = report_dict.get("rule_only_fields", [])
    llm_only_fields = report_dict.get("llm_only_fields", [])

    matched_field_count = len(consistent_fields)
    conflict_count = len(conflict_fields)
    total_distinct_fields = len(
        set(_extract_normalized_names(consistent_fields))
        | set(_extract_normalized_names(conflict_fields))
        | set(_extract_normalized_names(rule_only_fields))
        | set(_extract_normalized_names(llm_only_fields))
    )

    # 字段完整率：至少有一个引擎识别出值的字段占比
    fields_with_value = matched_field_count + conflict_count + len(rule_only_fields) + len(llm_only_fields)
    missed_field_count = max(0, total_distinct_fields - fields_with_value)

    # 字段准确率：一致或单引擎成功识别的字段 / 总字段
    field_accuracy = 0.0
    if total_distinct_fields > 0:
        field_accuracy = (fields_with_value / total_distinct_fields) * 100.0

    # 文档完整率简化为字段准确率（此处后续可补充关键字段缺失判断）
    document_completeness = field_accuracy

    diagnosis_snapshot = {
        "consistent_fields": consistent_fields,
        "conflict_fields": conflict_fields,
        "rule_only_fields": rule_only_fields,
        "llm_only_fields": llm_only_fields,
        "field_accuracy": round(field_accuracy, 2),
        "document_completeness": round(document_completeness, 2),
    }

    metric = ParseQualityMetric(
        source_file_id=source_file_id,
        file_name=file_name,
        document_type=document_type,
        rule_engine_used=1 if rule_engine_used else 0,
        llm_engine_used=1 if llm_engine_used else 0,
        field_count=total_distinct_fields,
        matched_field_count=fields_with_value,
        missed_field_count=missed_field_count,
        consistency_rate=round(consistency_rate * 100.0, 2),
        stability_score=round(stability_score * 100.0, 2),
        review_required=1 if review_required else 0,
        conflict_count=conflict_count,
        correction_applied_count=correction_applied_count,
        diagnosis_snapshot=diagnosis_snapshot,
    )

    db.add(metric)
    db.commit()
    db.refresh(metric)

    # 根据本次记录的创建日期更新对应日期的汇总，避免服务器时区/UTC 不一致导致日期错位。
    summary_date = metric.created_at.date() if metric.created_at else date.today()
    _update_daily_summary(db, document_type, summary_date)

    return metric


def _extract_normalized_names(field_items: list[Any]) -> list[str]:
    """从字段项列表中提取标准化字段名。"""
    names: list[str] = []
    for item in field_items:
        if isinstance(item, dict):
            normalized = item.get("normalized_field") or item.get("normalized_field_name")
            if normalized:
                names.append(normalized)
            elif item.get("field"):
                names.append(item["field"])
        else:
            # dataclass 对象
            normalized = getattr(item, "normalized_field", None) or getattr(item, "normalized_field_name", None)
            if normalized:
                names.append(normalized)
            elif getattr(item, "field", None):
                names.append(getattr(item, "field"))
    return names


def _comparison_report_to_dict(report: EngineComparisonReport) -> dict[str, Any]:
    """将 EngineComparisonReport 对象转换为字典。"""
    return {
        "consistency_rate": report.consistency_rate,
        "stability_score": report.stability_score,
        "review_required": report.review_required,
        "consistent_fields": report.consistent_fields,
        "conflict_fields": [
            {
                "field": f.field_name,
                "normalized_field": f.normalized_field_name,
                "rule_value": f.rule_value,
                "llm_value": f.llm_value,
            }
            for f in report.conflict_fields
        ],
        "rule_only_fields": [
            {
                "field": f.field_name,
                "normalized_field": f.normalized_field_name,
                "value": f.value,
            }
            for f in report.rule_only_fields
        ],
        "llm_only_fields": [
            {
                "field": f.field_name,
                "normalized_field": f.normalized_field_name,
                "value": f.value,
            }
            for f in report.llm_only_fields
        ],
    }


def _update_daily_summary(
    db: Session,
    document_type: str,
    summary_date: date | None = None,
) -> None:
    """
    更新指定文档类型和日期的汇总记录。

    业务逻辑：根据指定日期所有 ParseQualityMetric 记录重新计算聚合指标。

    Args:
        db: 数据库会话。
        document_type: 文档类型。
        summary_date: 汇总日期，默认为当天。
    """
    if summary_date is None:
        summary_date = date.today()

    summary_date_str = summary_date.isoformat()

    summary = db.query(ParseQualitySummary).filter_by(
        summary_date=summary_date_str, document_type=document_type
    ).first()

    if summary is None:
        summary = ParseQualitySummary(summary_date=summary_date_str, document_type=document_type)
        db.add(summary)

    # 重新统计该日期该类型的所有指标
    # 业务说明：由于 created_at 在 SQLite 下可能带时区，统一在 Python 中按日期过滤。
    all_metrics = db.query(ParseQualityMetric).filter(
        ParseQualityMetric.document_type == document_type,
    ).all()

    metrics = [
        m for m in all_metrics
        if m.created_at and m.created_at.date() == summary_date
    ]

    parse_count = len(metrics)
    if parse_count == 0:
        db.commit()
        return

    review_required_count = sum(1 for m in metrics if m.review_required)
    total_consistency = sum(m.consistency_rate for m in metrics)
    total_stability = sum(m.stability_score for m in metrics)
    total_field_count = sum(m.field_count for m in metrics)
    total_matched = sum(m.matched_field_count for m in metrics)
    total_correction = sum(m.correction_applied_count for m in metrics)

    summary.parse_count = parse_count
    summary.review_required_count = review_required_count
    summary.avg_consistency_rate = round(total_consistency / parse_count, 2)
    summary.avg_stability_score = round(total_stability / parse_count, 2)
    summary.overall_field_accuracy = round(
        (total_matched / total_field_count * 100.0) if total_field_count > 0 else 0.0, 2
    )
    summary.overall_document_completeness = summary.overall_field_accuracy
    summary.correction_applied_total = total_correction

    db.commit()


def get_quality_dashboard(
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
    document_type: str | None = None,
) -> dict[str, Any]:
    """
    获取解析稳定性看板数据。

    Args:
        db: 数据库会话。
        start_date: 开始日期（YYYY-MM-DD）。
        end_date: 结束日期（YYYY-MM-DD）。
        document_type: 文档类型过滤（可选）。

    Returns:
        dict: 包含汇总指标、趋势数据、复核分布的看板数据。
    """
    query = db.query(ParseQualitySummary)
    if start_date:
        query = query.filter(ParseQualitySummary.summary_date >= start_date)
    if end_date:
        query = query.filter(ParseQualitySummary.summary_date <= end_date)
    if document_type:
        query = query.filter(ParseQualitySummary.document_type == document_type)

    summaries = query.order_by(ParseQualitySummary.summary_date).all()

    total_parse_count = sum(s.parse_count for s in summaries)
    total_review_count = sum(s.review_required_count for s in summaries)
    weighted_consistency = sum(s.avg_consistency_rate * s.parse_count for s in summaries)
    weighted_stability = sum(s.avg_stability_score * s.parse_count for s in summaries)
    weighted_accuracy = sum(s.overall_field_accuracy * s.parse_count for s in summaries)
    weighted_completeness = sum(s.overall_document_completeness * s.parse_count for s in summaries)

    overall_consistency = round(
        weighted_consistency / total_parse_count if total_parse_count > 0 else 0.0, 2
    )
    overall_stability = round(
        weighted_stability / total_parse_count if total_parse_count > 0 else 0.0, 2
    )
    overall_accuracy = round(
        weighted_accuracy / total_parse_count if total_parse_count > 0 else 0.0, 2
    )
    overall_completeness = round(
        weighted_completeness / total_parse_count if total_parse_count > 0 else 0.0, 2
    )

    trend = [
        {
            "date": s.summary_date,
            "document_type": s.document_type,
            "parse_count": s.parse_count,
            "review_required_count": s.review_required_count,
            "avg_consistency_rate": s.avg_consistency_rate,
            "avg_stability_score": s.avg_stability_score,
            "overall_field_accuracy": s.overall_field_accuracy,
            "overall_document_completeness": s.overall_document_completeness,
            "correction_applied_total": s.correction_applied_total,
        }
        for s in summaries
    ]

    return {
        "total_parse_count": total_parse_count,
        "total_review_required_count": total_review_count,
        "overall_consistency_rate": overall_consistency,
        "overall_stability_score": overall_stability,
        "overall_field_accuracy": overall_accuracy,
        "overall_document_completeness": overall_completeness,
        "review_required_rate": round(
            total_review_count / total_parse_count * 100.0 if total_parse_count > 0 else 0.0, 2
        ),
        "trend": trend,
    }
