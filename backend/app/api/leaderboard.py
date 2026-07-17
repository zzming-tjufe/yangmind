from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import LeaderboardEntry, LeaderboardOut
from app.services.stats import build_leaderboard_rows

router = APIRouter(prefix="/api/v1", tags=["leaderboard"])


@router.get("/leaderboard", response_model=LeaderboardOut)
def leaderboard(
    period: str = Query(default="weekly", pattern="^(all|weekly)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """排行榜：weekly=本周已完成对局；all=历史累计。"""
    rows = build_leaderboard_rows(db, period=period)
    items = [
        LeaderboardEntry(
            rank=r["rank"],
            nickname=r["nickname"],
            public_id=r["public_id"],
            sessions_count=r["sessions_count"],
            personality_summary=r["personality_summary"],
            total_score=r["total_score"],
        )
        for r in rows
    ]
    return LeaderboardOut(period=period, items=items)
