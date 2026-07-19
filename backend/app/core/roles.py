"""角色常量与判断。兼容旧数据里的 role=admin（视为总管）。"""

from __future__ import annotations

from app.models.user import User

ROLE_SUPER = "super_admin"
ROLE_SUB = "sub_admin"
ROLE_PARTICIPANT = "participant"
# 历史兼容
ROLE_ADMIN_LEGACY = "admin"

SUPER_ROLES = frozenset({ROLE_SUPER, ROLE_ADMIN_LEGACY})
STAFF_ROLES = frozenset({ROLE_SUPER, ROLE_ADMIN_LEGACY, ROLE_SUB})

INVITE_KIND_SUB = "sub_admin"
INVITE_KIND_PARTICIPANT = "participant"
INVITE_KINDS = frozenset({INVITE_KIND_SUB, INVITE_KIND_PARTICIPANT})


def is_super_admin(user: User) -> bool:
    return user.role in SUPER_ROLES


def is_sub_admin(user: User) -> bool:
    return user.role == ROLE_SUB


def is_staff(user: User) -> bool:
    return user.role in STAFF_ROLES
