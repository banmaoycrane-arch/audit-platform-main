# -*- coding: utf-8 -*-
"""
模块功能：项目成员（ProjectMember）模型定义
业务场景：为项目分配团队成员，并指定角色（项目经理、审计员、复核人等）
政策依据：会计师事务所质量控制准则——项目组委派与职责分离
输入数据：项目ID、用户ID、角色
输出结果：数据库表 project_members，记录项目人员分派
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建 ProjectMember 关联模型
    2026-06-21  扩展角色体系，新增审计实务角色（partner/manager/senior/staff）
"""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# 审计实务角色枚举
AUDIT_ROLES = [
    "partner",        # 合伙人/项目负责人
    "manager",        # 经理/高级经理
    "senior",         # 高级审计员
    "staff",          # 审计员/初级人员
    "reviewer",       # 复核人
    "viewer",         # 查看者
    "leader",         # 现场带队（兼容旧角色）
    "member",         # 普通成员（兼容旧角色）
]


class ProjectMember(Base):
    """
    项目成员实体：记录"谁参与了哪个项目"以及"担任什么角色"
    对应审计实务中的"项目组成员表"，确保职责清晰、可追溯

    角色体系（审计实务）：
        - partner: 合伙人/项目负责人，负责项目承接、报告签发
        - manager: 经理/高级经理，负责项目执行、质量控制
        - senior: 高级审计员，负责现场带队、任务分配
        - staff: 审计员/初级人员，负责执行具体审计程序
        - reviewer: 复核人，负责复核底稿和报告
        - viewer: 查看者，只读权限
        - leader: 现场带队（兼容旧角色）
        - member: 普通成员（兼容旧角色）
    """
    __tablename__ = "project_members"

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="member"
    )  # partner / manager / senior / staff / reviewer / viewer / leader / member
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="members")
    user: Mapped["User"] = relationship("User")
