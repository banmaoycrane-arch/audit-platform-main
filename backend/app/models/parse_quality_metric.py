# -*- coding: utf-8 -*-
"""
模块功能：解析质量指标数据模型
业务场景：持久化每次文件解析的质量指标，支撑解析稳定性看板、趋势分析和质量改进。
政策依据：审计可追溯要求、持续质量改进的闭环管理。
输入数据：解析任务结果、双引擎对比报告、修正规则应用情况。
输出结果：可供聚合查询的解析质量指标记录。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建，定义解析质量指标模型。
"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ParseQualityMetric(Base):
    """
    解析质量指标记录

    业务含义：记录每一次文件解析的质量表现，包括字段识别准确率、
    文档完整率、双引擎一致性率、修正回流有效率等核心稳定性指标。
    """

    __tablename__ = "parse_quality_metric"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_file_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("source_files.id"), nullable=True, index=True,
        comment="关联的源文件ID"
    )

    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="原始文件名"
    )

    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="文档类型：contract/invoice/bank_statement/accounting_entry 等"
    )

    rule_engine_used: Mapped[bool] = mapped_column(
        Integer, default=1,
        comment="是否使用了规则引擎：1=是，0=否"
    )

    llm_engine_used: Mapped[bool] = mapped_column(
        Integer, default=1,
        comment="是否使用了LLM引擎：1=是，0=否"
    )

    field_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="本次解析涉及的标准字段总数"
    )

    matched_field_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="双引擎一致或单引擎成功识别的字段数"
    )

    missed_field_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="双引擎均未识别或识别为空的字段数"
    )

    consistency_rate: Mapped[float] = mapped_column(
        Integer, default=0,
        comment="双引擎字段一致性率（0-100）"
    )

    stability_score: Mapped[float] = mapped_column(
        Integer, default=0,
        comment="综合稳定性评分（0-100）"
    )

    review_required: Mapped[bool] = mapped_column(
        Integer, default=0,
        comment="是否需要人工复核：1=是，0=否"
    )

    conflict_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="双引擎字段冲突数"
    )

    correction_applied_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="本次解析应用的修正规则/补丁数"
    )

    diagnosis_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="解析诊断快照，包括一致/冲突字段明细"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True,
        comment="记录创建时间"
    )


class ParseQualitySummary(Base):
    """
    解析质量汇总记录

    业务含义：按天/文档类型聚合的解析质量指标，用于看板快速展示。
    """

    __tablename__ = "parse_quality_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    summary_date: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True,
        comment="汇总日期，格式 YYYY-MM-DD"
    )

    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="文档类型"
    )

    parse_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="解析次数"
    )

    review_required_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="需要复核次数"
    )

    avg_consistency_rate: Mapped[float] = mapped_column(
        Integer, default=0,
        comment="平均一致性率（0-100）"
    )

    avg_stability_score: Mapped[float] = mapped_column(
        Integer, default=0,
        comment="平均稳定性评分（0-100）"
    )

    overall_field_accuracy: Mapped[float] = mapped_column(
        Integer, default=0,
        comment="字段准确率（matched_field_count / (field_count * parse_count) 加权，0-100）"
    )

    overall_document_completeness: Mapped[float] = mapped_column(
        Integer, default=0,
        comment="文档完整率（有值的字段数 / 总字段数，0-100）"
    )

    correction_applied_total: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="累计应用修正规则数"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        comment="最后更新时间"
    )
