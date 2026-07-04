# -*- coding: utf-8 -*-
"""全局系统配置模型。"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class GlobalSettings(Base):
    """全局系统配置（如解析引擎配置）。"""

    __tablename__ = "global_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    settings_key: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    settings_value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )