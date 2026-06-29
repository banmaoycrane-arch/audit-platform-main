# -*- coding: utf-8 -*-
"""
模块功能：项目与账簿关联（ProjectLedger）模型定义
业务场景：一个审计/核算项目可能需要同时查看多个账簿（如集团审计）
政策依据：企业会计准则——合并报表与多主体审计范围界定
输入数据：项目ID、账簿ID
输出结果：数据库表 project_ledgers，记录项目与账簿的多对多关系
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建 ProjectLedger 关联模型
"""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ProjectLedger(Base):
    """
    项目账簿关联实体：记录"哪个项目包含哪些账簿"
    对应审计实务中的"审计范围清单"，明确项目覆盖的核算主体
    """
    __tablename__ = "project_ledgers"

    __table_args__ = (
        UniqueConstraint("project_id", "ledger_id", name="uq_project_ledger"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    ledger_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="ledgers")
    ledger: Mapped["Ledger"] = relationship("Ledger")
