# -*- coding: utf-8 -*-
"""
模块功能：用户账簿授权（UserLedgerAuth）模型定义
业务场景：记录每个用户对哪些账簿拥有访问权限，以及权限角色
政策依据：会计信息系统内部控制规范——职责分离与权限管理
输入数据：用户ID、账簿ID、角色、授权时间、授权人
输出结果：数据库表 user_ledger_auths，记录用户与账簿的授权关系
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建 UserLedgerAuth 模型
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.ledger import Ledger


class UserLedgerAuth(Base):
    """
    用户账簿授权实体：记录"谁可以操作哪个账簿"以及"什么角色"
    对应财务实务中的"权限分配表"，确保不相容职务分离
    """
    __tablename__ = "user_ledger_auths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    ledger_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ledgers.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    granted_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    user: Mapped["User"] = relationship(
        "User", foreign_keys=[user_id], back_populates="ledger_auths"
    )
    ledger: Mapped["Ledger"] = relationship(
        "Ledger", back_populates="ledger_auths"
    )
