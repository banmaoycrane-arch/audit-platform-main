# -*- coding: utf-8 -*-
"""
模块功能：账套（Ledger）模型定义
业务场景：每个团队（Team）可拥有多个独立账套，用于隔离不同客户或项目的财务数据
政策依据：企业会计准则——会计主体假设，不同核算主体数据必须物理隔离
输入数据：账套名称、所属团队、状态、数据库连接预留
输出结果：数据库表 ledgers，记录账套元信息
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建 Ledger 模型
"""
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Ledger(Base):
    """
    账套实体：对应财务实务中的"账簿"或"核算主体"
    每个账套拥有独立的科目、凭证、期间等数据，实现多账套隔离
    """
    __tablename__ = "ledgers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lifecycle_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    database_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    accounting_start_date: Mapped[date | None] = mapped_column(
        Date, nullable=True,
        comment="账套会计时间线起点；创建时默认当天，可自定义对齐历史建账",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    team: Mapped["Team"] = relationship("Team", back_populates="ledgers")
    ledger_auths: Mapped[list["UserLedgerAuth"]] = relationship(
        "UserLedgerAuth", back_populates="ledger"
    )
