# -*- coding: utf-8 -*-
"""
模块功能：账簿（Ledger）模型定义
业务场景：每个团队（Team）可拥有多个独立账簿，用于隔离不同客户或项目的财务数据
政策依据：企业会计准则——会计主体假设，不同核算主体数据必须物理隔离
输入数据：账簿名称、所属团队、状态、数据库连接预留
输出结果：数据库表 ledgers，记录账簿元信息
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建 Ledger 模型
"""
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.organization import Organization
    from app.models.user_ledger_auth import UserLedgerAuth


class Ledger(Base):
    """
    账簿（Ledger）：正式核算数据边界，是合同、发票、分录、审计测试的承上启下维度。

    新方案定位：核算账簿 / 法律单据承上启下维度。所有凭证、期间、期初余额、报表、审计数据
    均以 ledger_id 为最小过滤口径。Ledger 可归属于一个 Legal Entity（或 Reporting Entity）下的具体核算单元。

    与 Team 的关系：Team 是使用者协作边界，Ledger 是核算数据边界。
    与 Organization 的关系：Organization 是被执行对象背景，Ledger 是实际业务执行载体。
    """
    __tablename__ = "ledgers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    # 账簿所属的上层会计主体/组织；用于多账簿按组织汇总
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=True
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
        comment="账簿会计时间线起点；创建时默认当天，可自定义对齐历史建账",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    team: Mapped["Team"] = relationship("Team", back_populates="ledgers")
    organization: Mapped["Organization | None"] = relationship("Organization")
    ledger_auths: Mapped[list["UserLedgerAuth"]] = relationship(
        "UserLedgerAuth", back_populates="ledger"
    )
