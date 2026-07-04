from datetime import datetime, timezone, timedelta
import os
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import get_settings

os.environ["PASSLIB_BCRYPT_TRUNCATE"] = "true"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def _get_jwt_secret_key() -> str:
    settings = get_settings()
    if settings.secret_key:
        return settings.secret_key
    if settings.database_url.startswith("sqlite"):
        return "dev-local-jwt-secret-sqlite-only"
    raise RuntimeError("JWT 密钥未配置：请在后端环境变量 SECRET_KEY 中设置安全随机密钥")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)  # type: ignore[no-any-return]


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)  # type: ignore[no-any-return]


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    secret = _get_jwt_secret_key()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret, algorithm=ALGORITHM)
    return encoded_jwt  # type: ignore[no-any-return]


def decode_token(token: str) -> dict[str, Any] | None:
    secret = _get_jwt_secret_key()
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload  # type: ignore[no-any-return]
    except JWTError:
        return None
