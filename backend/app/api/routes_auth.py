from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import create_access_token
from app.services import auth_service
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str | None = None
    phone: str | None = None
    password: str
    agreed_terms: bool = False
    agreed_privacy: bool = False


class LoginPasswordRequest(BaseModel):
    username: str
    password: str


class LoginSmsRequest(BaseModel):
    phone: str
    code: str


class SmsCodeRequest(BaseModel):
    phone: str


class SetPasswordRequest(BaseModel):
    password: str


class SmsCodeResponse(BaseModel):
    code: str
    sms_code: str
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account_upgraded: bool = False


class UserResponse(BaseModel):
    id: int
    username: str | None
    phone: str | None
    email: str | None
    is_active: bool


class AuthContextResponse(BaseModel):
    user: dict
    teams: list[dict]
    ledgers: list[dict]
    projects: list[dict]
    current_ledger_id: int | None
    missing_bindings: list[str]
    requires_onboarding: bool
    next_action: str
    temporary_status: str
    historical_candidates: list[dict]
    mock_boundaries: dict


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if not payload.agreed_terms or not payload.agreed_privacy:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must agree to terms and privacy policy")

    username = payload.username.strip() if payload.username else None
    phone = payload.phone.strip() if payload.phone else None
    if not username and not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username or phone required")

    try:
        user, upgraded = auth_service.register_or_upgrade_user(
            db,
            username=username,
            phone=phone,
            password=payload.password,
            agreed_terms=payload.agreed_terms,
            agreed_privacy=payload.agreed_privacy,
        )
    except auth_service.RegisterConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or phone already exists",
        ) from None

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token, account_upgraded=upgraded)


@router.post("/login/password", response_model=TokenResponse)
def login_password(payload: LoginPasswordRequest, db: Session = Depends(get_db)):
    login_user = auth_service.get_password_login_user(db, payload.username)
    if not login_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在，请先注册或使用验证码登录")
    if not login_user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="该账号尚未设置密码，请使用验证码登录或注册后设置密码")
    user = auth_service.authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="密码错误，请重新输入")
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.post("/login/sms", response_model=TokenResponse)
def login_sms(payload: LoginSmsRequest, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user_by_sms(db, payload.phone, payload.code)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="验证码错误，请重新输入或重新获取")
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.post("/sms/code", response_model=SmsCodeResponse)
def sms_code(payload: SmsCodeRequest, db: Session = Depends(get_db)):
    code = auth_service.get_sms_code(db, payload.phone)
    return SmsCodeResponse(code=code, sms_code=code, message="验证码已生成")


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        phone=current_user.phone,
        email=current_user.email,
        is_active=current_user.is_active,
    )


@router.post("/password")
def set_password(
    payload: SetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if len(payload.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码至少需要 6 位")
    auth_service.set_user_password(db, current_user, payload.password)
    return {"status": "ok", "message": "密码已设置"}


@router.get("/context", response_model=AuthContextResponse)
def context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return auth_service.get_auth_context(db, current_user)
