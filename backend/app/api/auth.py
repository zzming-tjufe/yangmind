from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.admin_extra import AccountEvent, InviteCode
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _next_public_id(db: Session) -> str:
    count = db.scalar(func.count(User.id)) or 0
    return f"U-{1001 + count}"


def _role_for_email(email: str) -> str:
    return "admin" if email.lower().startswith("admin@") else "participant"


def _consume_invite(db: Session, raw: str | None) -> InviteCode | None:
    if not raw or not raw.strip():
        return None
    code = raw.strip().upper()
    invite = db.query(InviteCode).filter(InviteCode.code == code).first()
    if invite is None or not invite.enabled:
        raise HTTPException(status_code=400, detail="邀请码无效或已停用")
    if invite.max_uses > 0 and invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=400, detail="邀请码已用完")
    invite.used_count += 1
    return invite


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    exists = db.query(User).filter(User.email == email).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该邮箱已注册")

    invite = _consume_invite(db, body.invite_code)

    user = User(
        public_id=_next_public_id(db),
        email=email,
        password_hash=hash_password(body.password),
        nickname=body.nickname.strip(),
        role=_role_for_email(email),
        status="active",
    )
    db.add(user)
    db.flush()
    db.add(
        AccountEvent(
            user_id=user.id,
            event_type="register",
            detail=f"注册成功" + (f" · 邀请码 {invite.code}" if invite else ""),
        )
    )
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
