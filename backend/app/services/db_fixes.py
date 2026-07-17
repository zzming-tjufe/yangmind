"""启动时对已有 SQLite 库做轻量修补（去重 + 补唯一索引）。"""

from __future__ import annotations

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.survey import PersonalityScore, SurveyAnswer, SurveyResponse


def cleanup_duplicate_survey_responses(db: Session) -> int:
    """同一用户+量表只保留一条：优先 submitted，否则 id 最大的草稿。"""
    rows = (
        db.query(SurveyResponse.user_id, SurveyResponse.instrument_id)
        .group_by(SurveyResponse.user_id, SurveyResponse.instrument_id)
        .having(func.count(SurveyResponse.id) > 1)
        .all()
    )
    removed = 0
    for user_id, instrument_id in rows:
        responses = (
            db.query(SurveyResponse)
            .filter(
                SurveyResponse.user_id == user_id,
                SurveyResponse.instrument_id == instrument_id,
            )
            .order_by(SurveyResponse.id.asc())
            .all()
        )
        keep = next((r for r in responses if r.status == "submitted"), None)
        if keep is None:
            keep = responses[-1]
        for r in responses:
            if r.id == keep.id:
                continue
            db.query(PersonalityScore).filter(PersonalityScore.response_id == r.id).delete()
            db.query(SurveyAnswer).filter(SurveyAnswer.response_id == r.id).delete()
            db.delete(r)
            removed += 1
    if removed:
        db.commit()
    return removed


def ensure_survey_response_unique_index(engine) -> None:
    """为已有库补上唯一索引（create_all 不会改旧表结构）。"""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_instrument_response "
                "ON survey_responses (user_id, instrument_id)"
            )
        )
