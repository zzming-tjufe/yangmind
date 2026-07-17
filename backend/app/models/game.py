from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active")  # draft|active|archived
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    rounds_per_scene: Mapped[int] = mapped_column(Integer, default=10)

    scenes: Mapped[list["ExperimentScene"]] = relationship(back_populates="experiment")


class ExperimentScene(Base):
    __tablename__ = "experiment_scenes"
    __table_args__ = (UniqueConstraint("experiment_id", "scene_key", name="uq_scene_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    scene_key: Mapped[str] = mapped_column(String(64))
    no: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(128))
    short_desc: Mapped[str] = mapped_column(Text)
    option_a: Mapped[str] = mapped_column(String(128))
    option_b: Mapped[str] = mapped_column(String(128))
    option_a_text: Mapped[str] = mapped_column(Text)
    option_b_text: Mapped[str] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    experiment: Mapped["Experiment"] = relationship(back_populates="scenes")


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"))
    scene_id: Mapped[int] = mapped_column(ForeignKey("experiment_scenes.id"), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="bot")  # bot|matched|scripted
    bot_policy: Mapped[str] = mapped_column(String(64), default="coop_0.64")
    bot_seed: Mapped[int] = mapped_column(Integer, default=0)
    # intro 未使用；playing | finished | abandoned
    status: Mapped[str] = mapped_column(String(32), default="playing")
    current_round: Mapped[int] = mapped_column(Integer, default=1)
    my_score: Mapped[int] = mapped_column(Integer, default=0)
    opponent_score: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rounds: Mapped[list["GameRound"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    scene: Mapped["ExperimentScene"] = relationship()


class GameRound(Base):
    __tablename__ = "game_rounds"
    __table_args__ = (UniqueConstraint("session_id", "round_no", name="uq_session_round"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("game_sessions.id"), index=True)
    round_no: Mapped[int] = mapped_column(Integer)
    my_choice: Mapped[str] = mapped_column(String(1))  # A|B
    opponent_choice: Mapped[str] = mapped_column(String(1))
    my_points: Mapped[int] = mapped_column(Integer)
    opponent_points: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["GameSession"] = relationship(back_populates="rounds")
