"""子管数据范围：只能触达自己名下员工邀请码招来的参与者。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import false
from sqlalchemy.orm import Session

from app.core.roles import ROLE_PARTICIPANT, ROLE_SUB, is_super_admin
from app.models.admin_extra import InviteCode
from app.models.user import User


def owned_invite_ids(db: Session, sub_admin_id: int) -> list[int]:
    rows = (
        db.query(InviteCode.id)
        .filter(InviteCode.owner_id == sub_admin_id, InviteCode.kind == "participant")
        .all()
    )
    return [r[0] for r in rows]


def participant_query_for_staff(db: Session, staff: User):
    """返回员工用户查询：总管看全部 participant；子管只看名下。"""
    q = db.query(User).filter(User.role == ROLE_PARTICIPANT)
    if is_super_admin(staff):
        return q
    ids = owned_invite_ids(db, staff.id)
    if not ids:
        return q.filter(false())
    return q.filter(User.invited_by_code_id.in_(ids))


def assert_can_manage_participant(db: Session, staff: User, target: User | None) -> None:
    if target is None or target.role != ROLE_PARTICIPANT:
        raise HTTPException(status_code=404, detail="用户不存在")
    if is_super_admin(staff):
        return
    ids = owned_invite_ids(db, staff.id)
    if not target.invited_by_code_id or target.invited_by_code_id not in ids:
        raise HTTPException(status_code=403, detail="无权管理该用户")


def list_sub_admins(db: Session) -> list[User]:
    return db.query(User).filter(User.role == ROLE_SUB).order_by(User.id.asc()).all()
