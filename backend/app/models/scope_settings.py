# -*- coding: utf-8 -*-
"""账簿 / 团队 / 项目 / 主体 管理配置模型。"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LedgerSettings(Base):
    """账簿级会计政策与核算习惯配置。"""

    __tablename__ = "ledger_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[int] = mapped_column(
        ForeignKey("ledgers.id"), unique=True, index=True, nullable=False
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TeamSettings(Base):
    """团队级成员与权限策略配置。"""

    __tablename__ = "team_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"), unique=True, index=True, nullable=False
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProjectSettings(Base):
    """项目级合并与虚拟项目策略配置。"""

    __tablename__ = "project_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), unique=True, index=True, nullable=False
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EntityScopeSettings(Base):
    """账簿下会计主体（主体）管理策略配置。"""

    __tablename__ = "entity_scope_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[int] = mapped_column(
        ForeignKey("ledgers.id"), unique=True, index=True, nullable=False
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
