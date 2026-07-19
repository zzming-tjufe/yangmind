from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """用户表：谁注册了、密码哈希、角色。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(64))
    # participant | sub_admin | super_admin（旧数据可能仍是 admin）
    role: Mapped[str] = mapped_column(String(32), default="participant")
    status: Mapped[str] = mapped_column(String(32), default="active")
    # 注册所用邀请码 id（不建 FK，避免与 invite_codes 循环依赖）
    invited_by_code_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
