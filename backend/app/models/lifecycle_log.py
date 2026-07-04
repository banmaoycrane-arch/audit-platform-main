# -*- coding: utf-8 -*-
"""
模块功能：生命周期事件日志模型定义
业务场景：记录 Ledger 和 Project 等实体的生命周期状态变更，满足审计留痕要求
政策依据：会计信息系统内部控制规范——关键操作必须留痕，支持事后追溯
输入数据：实体类型、实体ID、操作类型、操作人、变更原因
输出结果：数据库表 lifecycle_logs，记录生命周期变更历史
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建 LifecycleLog 模型
"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LifecycleLog(Base):
    """
    生命周期日志实体：记录账簿、项目等关键业务对象的状态变更历史

    对应财务实务中的"操作日志"或"审计轨迹"，确保所有关键状态变更可追溯
    """
    __tablename__ = "lifecycle_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # ledger / project
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # activate / suspend / archive / restore / start / pause / complete / reopen / cancel
    previous_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    new_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    log_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    operator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
