from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.roles import (
    INVITE_KIND_PARTICIPANT,
    INVITE_KIND_SUB,
    ROLE_PARTICIPANT,
    ROLE_SUB,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.models.admin_extra import AccountEvent, InviteCode
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _next_public_id(db: Session) -> str:
    count = db.scalar(func.count(User.id)) or 0
    return f"U-{1001 + count}"


def _normalize_login(raw: str) -> str:
    """管理员可用别名 admin 登录；其余按邮箱处理。"""
    value = raw.lower().strip()
    alias = settings.seed_admin_login.lower().strip()
    if value == alias or value == "admin":
        return settings.seed_admin_email.lower().strip()
    return value


def _is_reserved_admin_identity(raw: str) -> bool:
    value = raw.lower().strip()
    return value in {
        settings.seed_admin_login.lower().strip(),
        "admin",
        settings.seed_admin_email.lower().strip(),
    }


def _consume_invite(db: Session, raw: str) -> InviteCode:
    """原子扣减邀请码次数，避免并发超发。注册强制要求有效邀请码。"""
    code = raw.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="请填写邀请码")

    invite = db.query(InviteCode).filter(InviteCode.code == code).first()
    if invite is None or not invite.enabled:
        raise HTTPException(status_code=400, detail="邀请码无效或已停用")

    kind = (invite.kind or INVITE_KIND_PARTICIPANT).strip()
    if kind == INVITE_KIND_PARTICIPANT and invite.owner_id is None:
        raise HTTPException(
            status_code=400,
            detail="该员工邀请码尚未分配给子管理员，暂时无法使用",
        )

    filters = [
        InviteCode.id == invite.id,
        InviteCode.enabled.is_(True),
    ]
    if invite.max_uses > 0:
        filters.append(InviteCode.used_count < InviteCode.max_uses)

    updated = (
        db.query(InviteCode)
        .filter(and_(*filters))
        .update(
            {InviteCode.used_count: InviteCode.used_count + 1},
            synchronize_session=False,
        )
    )
    if updated != 1:
        raise HTTPException(status_code=400, detail="邀请码已用完")

    db.refresh(invite)
    return invite


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    nickname = body.nickname.strip()
    if not nickname:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入昵称")
    if _is_reserved_admin_identity(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该账号为系统保留，请更换邮箱")

    exists = db.query(User).filter(User.email == email).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该邮箱已注册")

    invite = _consume_invite(db, body.invite_code)
    kind = (invite.kind or INVITE_KIND_PARTICIPANT).strip()
    if kind == INVITE_KIND_SUB:
        role = ROLE_SUB
    elif kind == INVITE_KIND_PARTICIPANT:
        role = ROLE_PARTICIPANT
    else:
        raise HTTPException(status_code=400, detail="邀请码类型无效")

    user = User(
        public_id=_next_public_id(db),
        email=email,
        password_hash=hash_password(body.password),
        nickname=nickname,
        role=role,
        status="active",
        invited_by_code_id=invite.id,
    )
    db.add(user)
    db.flush()
    db.add(
        AccountEvent(
            user_id=user.id,
            event_type="register",
            detail=f"注册成功 · 邀请码 {invite.code} · 角色 {role}",
        )
    )
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = _normalize_login(body.email)
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """参与者 / 管理员自助修改密码（需验证当前密码）。"""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能与当前密码相同")

    current_user.password_hash = hash_password(body.new_password)
    db.add(
        AccountEvent(
            user_id=current_user.id,
            actor_id=current_user.id,
            event_type="change_password",
            detail="用户自助修改密码",
        )
    )
    db.commit()
    return {"ok": True}
