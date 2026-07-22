"""角色常量与判断。兼容旧数据里的 role=admin（视为总管）。"""

from __future__ import annotations

from app.models.user import User

ROLE_SUDO = "sudo"
ROLE_SUPER = "super_admin"
ROLE_SUB = "sub_admin"
ROLE_PARTICIPANT = "participant"
# 历史兼容
ROLE_ADMIN_LEGACY = "admin"

# 总管能力（含更高的 sudo）
SUPER_ROLES = frozenset({ROLE_SUDO, ROLE_SUPER, ROLE_ADMIN_LEGACY})
STAFF_ROLES = frozenset({ROLE_SUDO, ROLE_SUPER, ROLE_ADMIN_LEGACY, ROLE_SUB})

INVITE_KIND_SUB = "sub_admin"
INVITE_KIND_PARTICIPANT = "participant"
INVITE_KINDS = frozenset({INVITE_KIND_SUB, INVITE_KIND_PARTICIPANT})


def is_sudo(user: User) -> bool:
    """调试账号：权限覆盖总管，另有视角切换等专属能力。"""
    return user.role == ROLE_SUDO


def is_super_admin(user: User) -> bool:
    """总管或 sudo（sudo 可调用所有总管接口）。"""
    return user.role in SUPER_ROLES


def is_sub_admin(user: User) -> bool:
    return user.role == ROLE_SUB


def is_staff(user: User) -> bool:
    return user.role in STAFF_ROLES


def user_is_debug(user: User) -> bool:
    """调试标签：sudo 本人，或经调试邀请码注册的用户。"""
    if is_sudo(user):
        return True
    return bool(getattr(user, "is_debug", False))
