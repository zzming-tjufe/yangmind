"""启动时对已有库做轻量修补（去重 + 补唯一索引 + 补 RBAC 列）。"""

from __future__ import annotations

from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from app.models.survey import PersonalityScore, SurveyAnswer, SurveyResponse


def _existing_columns(engine, table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def ensure_rbac_schema(engine) -> None:
    """为已有库补上多层权限相关列（create_all 不会改旧表）。"""
    user_cols = _existing_columns(engine, "users")
    invite_cols = _existing_columns(engine, "invite_codes")
    stmts: list[str] = []
    if "users" in inspect(engine).get_table_names() and "invited_by_code_id" not in user_cols:
        stmts.append("ALTER TABLE users ADD COLUMN invited_by_code_id INTEGER")
    if "invite_codes" in inspect(engine).get_table_names():
        if "kind" not in invite_cols:
            stmts.append(
                "ALTER TABLE invite_codes ADD COLUMN kind VARCHAR(32) DEFAULT 'participant'"
            )
        if "owner_id" not in invite_cols:
            stmts.append("ALTER TABLE invite_codes ADD COLUMN owner_id INTEGER")
    if not stmts:
        return
    with engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))
        # 旧邀请码统一标成员工码
        if "kind" not in invite_cols:
            conn.execute(
                text(
                    "UPDATE invite_codes SET kind = 'participant' "
                    "WHERE kind IS NULL OR kind = ''"
                )
            )



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
