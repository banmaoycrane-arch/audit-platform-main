from app.models.user import User

SUPER_ADMIN_ROLE = "super_admin"


def is_super_admin(user: User | None) -> bool:
    return bool(user and getattr(user, "platform_role", "user") == SUPER_ADMIN_ROLE)


def require_super_admin(user: User) -> None:
    if not is_super_admin(user):
        raise PermissionError("需要开发者超级管理员权限")
