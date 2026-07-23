"""sudo 调试账号：清空本人正式实验进度，回到未作答、未对局状态。"""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.game import GameComprehension, GameRound, GameSession
from app.models.match import PvpDecisionTelemetry, PvpMatch, PvpRound
from app.models.survey import (
    PersonalityScore,
    SurveyAnswer,
    SurveyQualityTelemetry,
    SurveyResponse,
    SurveyRetakeArchive,
)
from app.models.user import User


def reset_sudo_progress(db: Session, user: User) -> dict[str, int]:
    """
    删除该用户问卷、理解检查、对局会话与相关真人匹配。
    若曾与他人配对，整场 match 及双方 session 一并清除（调试用途）。
    """
    uid = user.id
    matches = (
        db.query(PvpMatch)
        .filter(or_(PvpMatch.user_a_id == uid, PvpMatch.user_b_id == uid))
        .all()
    )
    match_ids = [m.id for m in matches]
    session_ids: set[int] = set(
        sid
        for m in matches
        for sid in (m.session_a_id, m.session_b_id)
        if sid is not None
    )
    own_session_ids = {
        row.id
        for row in db.query(GameSession.id).filter(GameSession.user_id == uid).all()
    }
    session_ids |= own_session_ids

    deleted = {
        "matches": len(match_ids),
        "sessions": len(session_ids),
        "survey_responses": 0,
        "comprehension": 0,
        "retake_archives": 0,
    }

    if match_ids:
        db.query(PvpDecisionTelemetry).filter(
            PvpDecisionTelemetry.match_id.in_(match_ids)
        ).delete(synchronize_session=False)
        db.query(PvpRound).filter(PvpRound.match_id.in_(match_ids)).delete(
            synchronize_session=False
        )
        db.query(PvpMatch).filter(PvpMatch.id.in_(match_ids)).update(
            {PvpMatch.session_a_id: None, PvpMatch.session_b_id: None},
            synchronize_session=False,
        )

    if session_ids:
        db.query(GameRound).filter(GameRound.session_id.in_(session_ids)).delete(
            synchronize_session=False
        )
        db.query(GameSession).filter(GameSession.id.in_(session_ids)).delete(
            synchronize_session=False
        )

    if match_ids:
        db.query(PvpMatch).filter(PvpMatch.id.in_(match_ids)).delete(
            synchronize_session=False
        )

    deleted["comprehension"] = (
        db.query(GameComprehension)
        .filter(GameComprehension.user_id == uid)
        .delete(synchronize_session=False)
    )

    response_ids = [
        row.id
        for row in db.query(SurveyResponse.id).filter(SurveyResponse.user_id == uid).all()
    ]
    if response_ids:
        db.query(PersonalityScore).filter(
            PersonalityScore.response_id.in_(response_ids)
        ).delete(synchronize_session=False)
        db.query(SurveyQualityTelemetry).filter(
            SurveyQualityTelemetry.response_id.in_(response_ids)
        ).delete(synchronize_session=False)
        db.query(SurveyAnswer).filter(SurveyAnswer.response_id.in_(response_ids)).delete(
            synchronize_session=False
        )
        deleted["survey_responses"] = (
            db.query(SurveyResponse)
            .filter(SurveyResponse.id.in_(response_ids))
            .delete(synchronize_session=False)
        )

    db.query(PersonalityScore).filter(PersonalityScore.user_id == uid).delete(
        synchronize_session=False
    )
    db.query(SurveyQualityTelemetry).filter(SurveyQualityTelemetry.user_id == uid).delete(
        synchronize_session=False
    )
    deleted["retake_archives"] = (
        db.query(SurveyRetakeArchive)
        .filter(SurveyRetakeArchive.user_id == uid)
        .delete(synchronize_session=False)
    )

    return deleted
