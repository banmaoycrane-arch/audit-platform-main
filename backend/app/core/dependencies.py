from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_token
from app.services.auth_service import get_user_by_id
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.services import ledger_management_service

security = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security), db: Session = Depends(get_db)):
    """
    获取当前用户。

    从请求 Header 的 Bearer Token 中解码用户ID，查询数据库返回用户对象。
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = get_user_by_id(db, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def get_current_ledger(
    x_ledger_id: int | None = Header(None, alias="X-Ledger-Id"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int | None:
    """
    获取当前账套ID。

    业务逻辑：优先从请求 Header X-Ledger-Id 获取，
    若 Header 未提供，则回退到 user.last_ledger_id。

    Args:
        x_ledger_id: 请求头中的账套ID
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        int | None: 当前账套ID，若未指定则返回 None
    """
    ledger_id = x_ledger_id or current_user.last_ledger_id
    if ledger_id is None:
        return None

    # 验证用户是否有该账套访问权限
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"用户无权访问账套 {ledger_id}",
        )

    return ledger_id
