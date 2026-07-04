# -*- coding: utf-8 -*-
"""
模块功能：项目服务（存根实现）
业务场景：为绑定申请审批后写入项目成员关系
政策依据：会计信息系统内部控制规范——项目成员授权需审批
输入数据：数据库会话、项目ID、用户ID、角色
输出结果：项目成员关系
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建存根实现，避免导入错误
"""
from typing import Any


def assign_member_to_project(
    db: Any,
    project_id: int,
    user_id: int,
    role: str = "member",
) -> dict[str, Any]:
    """
    将用户分配为项目成员。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID
        role: 项目角色

    Returns:
        dict[str, Any]: 操作结果，当前存根实现返回空结果
    """
    return {"project_id": project_id, "user_id": user_id, "role": role, "status": "stub"}
