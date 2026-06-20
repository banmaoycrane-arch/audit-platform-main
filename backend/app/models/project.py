# -*- coding: utf-8 -*-
"""
模块功能：项目管理（Project）模型定义
业务场景：审计或核算项目，用于归集多个账套、分配团队成员、跟踪项目进度
政策依据：会计师事务所质量控制准则——项目立项与人员分派
输入数据：项目名称、所属团队、项目类型、状态、起止日期、负责人
输出结果：数据库表 projects，记录项目元信息
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建 Project 模型
"""
from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Project(Base):
    """
    项目实体：对应审计实务中的"审计项目"或核算实务中的"核算项目"
    一个项目可关联多个账套，并分配多名团队成员
    """
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(
        String(50), default="audit"
    )  # audit / accounting / tax / consulting
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )  # active / paused / completed / cancelled
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lifecycle_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    manager_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    team: Mapped["Team"] = relationship("Team", back_populates="projects")
    manager: Mapped["User"] = relationship("User")
    ledgers: Mapped[list["ProjectLedger"]] = relationship(
        "ProjectLedger", back_populates="project", cascade="all, delete-orphan"
    )
    members: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="project", cascade="all, delete-orphan"
    )
