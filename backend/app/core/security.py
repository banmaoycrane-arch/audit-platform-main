import bcrypt
from datetime import datetime, timedelta
import os
from jose import JWTError, jwt
from app.core.config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


class AuthConfigurationError(RuntimeError):
    """认证配置缺失，例如未设置 SECRET_KEY。"""


def _get_jwt_secret_key() -> str:
    settings = get_settings()
    secret = (settings.secret_key or "").strip()
    if not secret:
        raise AuthConfigurationError(
            "JWT 密钥未配置：请在 backend/.env 或环境变量 SECRET_KEY 中设置安全随机密钥"
        )
    return secret


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    secret = _get_jwt_secret_key()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict | None:
    secret = _get_jwt_secret_key()
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
