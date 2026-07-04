# -*- coding: utf-8 -*-
"""
模块功能：解析修正数据模型
业务场景：存储人工复核对解析结果的修正，用于规则提取和自动学习
政策依据：审计追踪要求、机器学习反馈闭环最佳实践
输入数据：解析任务ID、文档类型、原始解析结果、修正后结果、修正原因
输出结果：持久化的修正记录，支撑规则提取和回归验证
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建，实现修正记录数据模型
"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ParseCorrection(Base):
    """
    解析修正记录
    
    业务含义：记录人工复核对解析结果的修正，用于后续规则提取和自动学习。
    每条记录包含原始解析结果和修正后结果的差异，是系统自愈能力的基础数据。
    """

    __tablename__ = "parse_correction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    task_id: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False,
        comment="解析任务ID，关联原始解析请求"
    )
    
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="文档类型：invoice/bank_statement/contract等"
    )
    
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="原始文件名"
    )
    
    original_result: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False,
        comment="原始解析结果（规则引擎或LLM引擎输出）"
    )
    
    corrected_result: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False,
        comment="人工修正后的结果"
    )
    
    diff_fields: Mapped[list[str]] = mapped_column(
        JSON, nullable=False,
        comment="发生变更的字段列表"
    )
    
    correction_reason: Mapped[str] = mapped_column(
        Text, nullable=True,
        comment="修正原因说明"
    )
    
    corrected_by: Mapped[str] = mapped_column(
        String(100), nullable=True,
        comment="修正人"
    )
    
    status: Mapped[str] = mapped_column(
        String(20), default="pending",
        comment="状态：pending(待处理)/analyzed(已分析)/applied(已应用)/rejected(已拒绝)"
    )
    
    rule_extracted: Mapped[bool] = mapped_column(
        Integer, default=0,
        comment="是否已提取规则：0=未提取，1=已提取"
    )
    
    extracted_rule: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=True,
        comment="从修正中提取的规则（正则表达式、模板等）"
    )
    
    regression_passed: Mapped[bool] = mapped_column(
        Integer, default=0,
        comment="回归验证是否通过：0=未验证，1=通过，-1=失败"
    )
    
    regression_log: Mapped[str] = mapped_column(
        Text, nullable=True,
        comment="回归验证日志"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ParsingRulePatch(Base):
    """
    解析规则补丁
    
    业务含义：从修正记录中提取的规则补丁，经过回归验证后可以动态应用到规则引擎。
    支持正则表达式、字段映射、提取模板等多种规则类型。
    """

    __tablename__ = "parsing_rule_patch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    rule_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="规则名称"
    )
    
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="适用文档类型"
    )
    
    rule_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="规则类型：regex(正则)/template(模板)/mapping(映射)"
    )
    
    rule_pattern: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="规则模式（正则表达式、模板字符串等）"
    )
    
    target_field: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="目标字段名"
    )
    
    priority: Mapped[int] = mapped_column(
        Integer, default=50,
        comment="优先级（数值越小优先级越高）"
    )
    
    confidence_boost: Mapped[float] = mapped_column(
        Integer, default=0,
        comment="置信度提升值（0-10）"
    )
    
    status: Mapped[str] = mapped_column(
        String(20), default="draft",
        comment="状态：draft(草稿)/active(生效)/disabled(禁用)"
    )
    
    source_correction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parse_correction.id"), nullable=True,
        comment="来源修正记录ID"
    )
    
    applied_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="应用次数"
    )
    
    success_rate: Mapped[float] = mapped_column(
        Integer, default=0,
        comment="成功率（0-100）"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )