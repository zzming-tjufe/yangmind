from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.game import GameRound, GameSession
from app.models.survey import PersonalityScore, SurveyResponse
from app.models.user import User


def user_game_stats(db: Session, user_id: int) -> tuple[int, int]:
    """返回 (总得分, 已完成场次)。"""
    total = (
        db.query(func.coalesce(func.sum(GameSession.my_score), 0))
        .filter(GameSession.user_id == user_id, GameSession.status == "finished")
        .scalar()
    )
    count = (
        db.query(func.count(GameSession.id))
        .filter(GameSession.user_id == user_id, GameSession.status == "finished")
        .scalar()
    )
    return int(total or 0), int(count or 0)


def latest_personality(db: Session, user_id: int) -> PersonalityScore | None:
    return (
        db.query(PersonalityScore)
        .filter(PersonalityScore.user_id == user_id)
        .order_by(PersonalityScore.id.desc())
        .first()
    )


def survey_status_for_user(db: Session, user_id: int) -> str:
    submitted = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.user_id == user_id, SurveyResponse.status == "submitted")
        .first()
    )
    return "已完成" if submitted else "未完成"


def build_leaderboard_rows(db: Session) -> list[dict]:
    users = (
        db.query(User)
        .filter(User.role == "participant", User.status == "active")
        .all()
    )
    rows = []
    for u in users:
        total, sessions = user_game_stats(db, u.id)
        personality = latest_personality(db, u.id)
        rows.append(
            {
                "user_id": u.id,
                "nickname": u.nickname,
                "public_id": u.public_id,
                "total_score": total,
                "sessions_count": sessions,
                "personality_summary": personality.summary_label if personality else "待生成",
                "survey_status": survey_status_for_user(db, u.id),
            }
        )
    rows.sort(key=lambda x: (-x["total_score"], -x["sessions_count"], x["public_id"]))
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows


def admin_overview_stats(db: Session) -> dict:
    total_users = db.query(func.count(User.id)).filter(User.role == "participant").scalar() or 0
    submitted = (
        db.query(func.count(func.distinct(SurveyResponse.user_id)))
        .filter(SurveyResponse.status == "submitted")
        .scalar()
        or 0
    )
    completion_rate = round(submitted / total_users * 100, 1) if total_users else 0.0

    valid_rounds = (
        db.query(func.count(GameRound.id))
        .join(GameSession, GameRound.session_id == GameSession.id)
        .filter(GameSession.status == "finished")
        .scalar()
        or 0
    )
    coop_rounds = (
        db.query(func.count(GameRound.id))
        .join(GameSession, GameRound.session_id == GameSession.id)
        .filter(GameSession.status == "finished", GameRound.my_choice == "A")
        .scalar()
        or 0
    )
    coop_rate = round(coop_rounds / valid_rounds * 100, 1) if valid_rounds else 0.0

    return {
        "total_users": int(total_users),
        "survey_completion_rate": completion_rate,
        "valid_rounds": int(valid_rounds),
        "avg_coop_rate": coop_rate,
    }
