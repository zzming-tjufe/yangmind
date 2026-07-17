from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


class SurveyInstrument(Base):
    """问卷量表，如 BFI-44。"""

    __tablename__ = "survey_instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    version: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128))
    item_count: Mapped[int] = mapped_column(Integer)

    items: Mapped[list["SurveyItem"]] = relationship(back_populates="instrument")


class SurveyItem(Base):
    """单道题目。"""

    __tablename__ = "survey_items"
    __table_args__ = (UniqueConstraint("instrument_id", "item_no", name="uq_item_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("survey_instruments.id"))
    item_no: Mapped[int] = mapped_column(Integer)
    stem: Mapped[str] = mapped_column(Text)
    dimension: Mapped[str] = mapped_column(String(1))  # E/A/C/N/O
    reverse_scored: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer)

    instrument: Mapped["SurveyInstrument"] = relationship(back_populates="items")


class SurveyResponse(Base):
    """某用户对某量表的一份答卷。"""

    __tablename__ = "survey_responses"
    __table_args__ = (
        UniqueConstraint("user_id", "instrument_id", name="uq_user_instrument_response"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("survey_instruments.id"))
    instrument_version: Mapped[str] = mapped_column(String(32))
    # in_progress | submitted
    status: Mapped[str] = mapped_column(String(32), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quality_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    answers: Mapped[list["SurveyAnswer"]] = relationship(
        back_populates="response", cascade="all, delete-orphan"
    )
    personality_score: Mapped["PersonalityScore | None"] = relationship(
        back_populates="response", uselist=False, cascade="all, delete-orphan"
    )


class SurveyAnswer(Base):
    """某一题的作答（1-5）。"""

    __tablename__ = "survey_answers"
    __table_args__ = (UniqueConstraint("response_id", "item_no", name="uq_response_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("survey_responses.id"), index=True)
    item_no: Mapped[int] = mapped_column(Integer)
    value: Mapped[int] = mapped_column(Integer)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    response: Mapped["SurveyResponse"] = relationship(back_populates="answers")


class PersonalityScore(Base):
    """提交后算出的五维分数。"""

    __tablename__ = "personality_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("survey_responses.id"), unique=True)
    e: Mapped[float] = mapped_column(Float)
    a: Mapped[float] = mapped_column(Float)
    c: Mapped[float] = mapped_column(Float)
    n: Mapped[float] = mapped_column(Float)
    o: Mapped[float] = mapped_column(Float)
    summary_label: Mapped[str] = mapped_column(String(128))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    response: Mapped["SurveyResponse"] = relationship(back_populates="personality_score")
