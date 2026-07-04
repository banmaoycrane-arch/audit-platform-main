# -*- coding: utf-8 -*-
"""
模块功能：平台权限服务
业务场景：超级管理员权限控制、平台级角色判断
政策依据：会计信息系统内部控制要求，敏感操作必须由超级管理员执行
输入数据：用户对象
输出结果：权限判断结果
创建日期：2026-06-01
更新记录：
    2025-01-20  封装为 PlatformPermissionService 类
"""
from app.models.user import User

SUPER_ADMIN_ROLE = "super_admin"


class PlatformPermissionService:
    """
    平台权限服务
    
    功能描述：提供平台级权限判断和控制
    业务逻辑：判断用户是否为超级管理员，验证敏感操作权限
    会计口径：超级管理员权限用于系统级操作，不参与具体会计核算
    
    注意事项：
        1. SUPER_ADMIN_ROLE 定义了超级管理员角色标识
    """
    
    def is_super_admin(self, user: User | None) -> bool:
        """
        判断用户是否为超级管理员
        
        Args:
            user: 用户对象（可为 None）
            
        Returns:
            bool: 是否为超级管理员
        """
        return bool(user and getattr(user, "platform_role", "user") == SUPER_ADMIN_ROLE)

    def require_super_admin(self, user: User) -> None:
        """
        要求用户必须为超级管理员，否则抛出权限错误
        
        Args:
            user: 用户对象
            
        Raises:
            PermissionError: 非超级管理员时抛出
        """
        if not self.is_super_admin(user):
            raise PermissionError("需要开发者超级管理员权限")


# 向后兼容的函数包装器
_platform_permission_service_instance = PlatformPermissionService()


def is_super_admin(user: User | None) -> bool:
    return _platform_permission_service_instance.is_super_admin(user)


def require_super_admin(user: User) -> None:
    return _platform_permission_service_instance.require_super_admin(user)
