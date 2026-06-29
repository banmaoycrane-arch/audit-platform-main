# -*- coding: utf-8 -*-
"""
模块功能：用户绑定申请模型定义
业务场景：访客用户申请加入团队、访问账簿、关联项目，并等待管理员审批
政策依据：会计信息系统内部控制规范——权限申请、审批与授权留痕
输入数据：申请人、目标团队、账簿、项目和申请角色
输出结果：binding_requests 表，记录绑定申请及审批结果
创建日期：2026-06-20
更新记录：
    2026-06-20  初始创建绑定申请模型
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class BindingRequest(Base):
    """
    用户绑定申请实体：记录“谁申请加入哪个团队、访问哪个账簿、关联哪个项目”。
    对应财务实务中的权限申请单，审批通过后才写入正式授权关系。
    """
    __tablename__ = "binding_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    requester_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    ledger_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ledgers.id"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True)
    requested_role: Mapped[str] = mapped_column(String(50), nullable=False, default="viewer")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    requester: Mapped["User"] = relationship("User", foreign_keys=[requester_user_id])
