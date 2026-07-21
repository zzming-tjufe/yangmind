from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.roles import (
    INVITE_KIND_PARTICIPANT,
    INVITE_KIND_SUB,
    INVITE_KINDS,
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


def _public_id_for_user(user_id: int) -> str:
    return f"U-{1000 + user_id}"


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


def _load_valid_invite(db: Session, raw: str) -> InviteCode:
    """校验邀请码可用性（不扣次数）。"""
    code = raw.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="请填写邀请码")

    invite = db.query(InviteCode).filter(InviteCode.code == code).first()
    if invite is None or not invite.enabled:
        raise HTTPException(status_code=400, detail="邀请码无效或已停用")

    kind = (invite.kind or INVITE_KIND_PARTICIPANT).strip()
    if kind not in INVITE_KINDS:
        raise HTTPException(status_code=400, detail="邀请码类型无效")
    if kind == INVITE_KIND_PARTICIPANT and invite.owner_id is None:
        raise HTTPException(
            status_code=400,
            detail="该员工邀请码尚未分配给子管理员，暂时无法使用",
        )
    if invite.max_uses > 0 and invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=400, detail="邀请码已用完")
    return invite


def _consume_invite(db: Session, invite: InviteCode) -> InviteCode:
    """原子扣减邀请码次数；与用户创建同事务，失败由调用方 rollback。"""
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

    invite = _load_valid_invite(db, body.invite_code)
    kind = (invite.kind or INVITE_KIND_PARTICIPANT).strip()
    role = ROLE_SUB if kind == INVITE_KIND_SUB else ROLE_PARTICIPANT

    try:
        invite = _consume_invite(db, invite)
        user = User(
            # The final public id is derived from the database-generated primary key.
            # A unique placeholder lets concurrent inserts safely reach the first flush.
            # 占位须 ≤ public_id 列宽（32）；正式值在 flush 后写成 U-{1000+id}
            public_id=f"P-{uuid4().hex[:28]}",
            email=email,
            password_hash=hash_password(body.password),
            nickname=nickname,
            role=role,
            status="active",
            invited_by_code_id=invite.id,
        )
        db.add(user)
        db.flush()
        user.public_id = _public_id_for_user(user.id)
        db.add(
            AccountEvent(
                user_id=user.id,
                event_type="register",
                detail=f"使用邀请码 {invite.code} 注册成功，角色为{'子管理员' if role == ROLE_SUB else '参与者'}",
            )
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="注册请求发生冲突，请重试；若邮箱已注册请直接登录",
        ) from None
    except Exception:
        db.rollback()
        raise
    db.refresh(user)

    token = create_access_token(user.id, user.password_hash)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = _normalize_login(body.email)
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = create_access_token(user.id, user.password_hash)
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
