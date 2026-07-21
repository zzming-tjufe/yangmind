"""真人匹配对局表。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# 每轮选择时限（秒）
PVP_ROUND_TIMEOUT_SEC = 15


class PvpMatch(Base):
    """双人同步对局。"""

    __tablename__ = "pvp_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("experiment_scenes.id"), index=True)
    # waiting | playing | finished | cancelled
    status: Mapped[str] = mapped_column(String(32), default="waiting", index=True)
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_b_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    rounds_total: Mapped[int] = mapped_column(Integer, default=10)
    current_round: Mapped[int] = mapped_column(Integer, default=1)
    round_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score_a: Mapped[int] = mapped_column(Integer, default=0)
    score_b: Mapped[int] = mapped_column(Integer, default=0)
    session_a_id: Mapped[int | None] = mapped_column(ForeignKey("game_sessions.id"), nullable=True)
    session_b_id: Mapped[int | None] = mapped_column(ForeignKey("game_sessions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rounds: Mapped[list["PvpRound"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="PvpRound.round_no",
    )


class PvpRound(Base):
    __tablename__ = "pvp_rounds"
    __table_args__ = (UniqueConstraint("match_id", "round_no", name="uq_pvp_match_round"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("pvp_matches.id"), index=True)
    round_no: Mapped[int] = mapped_column(Integer)
    # open | resolved
    status: Mapped[str] = mapped_column(String(32), default="open")
    choice_a: Mapped[str | None] = mapped_column(String(1), nullable=True)
    choice_b: Mapped[str | None] = mapped_column(String(1), nullable=True)
    a_timed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    b_timed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    points_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    match: Mapped["PvpMatch"] = relationship(back_populates="rounds")


class PvpDecisionTelemetry(Base):
    """每轮每位真人参与者首次提交选择的反应时。"""

    __tablename__ = "pvp_decision_telemetry"
    __table_args__ = (
        UniqueConstraint("match_id", "round_no", "user_id", name="uq_pvp_decision_user_round"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("pvp_matches.id"), index=True)
    round_no: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    decision_ms: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
