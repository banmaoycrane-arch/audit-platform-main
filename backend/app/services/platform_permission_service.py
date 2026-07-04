# -*- coding: utf-8 -*-
"""
模块功能：平台权限服务（存根实现）
业务场景：判断用户是否为超级管理员等全局权限
政策依据：会计信息系统内部控制规范——关键权限需分离
输入数据：用户对象
输出结果：权限判断结果
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建存根实现，避免导入错误
"""
from typing import Any


def is_super_admin(user: Any | None) -> bool:
    """
    判断用户是否为平台超级管理员。

    Args:
        user: 用户对象

    Returns:
        bool: 当前存根实现始终返回 False，避免越权
    """
    return False
