from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.game import Experiment, ExperimentScene, GameRound, GameSession
from app.models.match import PVP_ROUND_TIMEOUT_SEC, PvpMatch, PvpRound
from app.models.user import User
from app.services.pvp_engine import resolve_pvp_payoff


def _now() -> datetime:
    """统一用无时区 UTC，避免 SQLite 读写后出现 naive/aware 混比。"""
    return datetime.now(UTC).replace(tzinfo=None)


def _as_utc(dt: datetime | None) -> datetime | None:
    """兼容历史 aware 值与 SQLite 读出的 naive 时间。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


def start_round(db: Session, match: PvpMatch) -> PvpRound:
    """开启新一轮并设置截止时间。"""
    rnd = PvpRound(match_id=match.id, round_no=match.current_round, status="open")
    db.add(rnd)
    match.round_deadline = _now() + timedelta(seconds=PVP_ROUND_TIMEOUT_SEC)
    db.flush()
    return rnd


def current_open_round(db: Session, match: PvpMatch) -> PvpRound | None:
    """从数据库查当前 open 轮，避免 relationship 缓存导致串轮/空轮。"""
    return (
        db.query(PvpRound)
        .filter(
            PvpRound.match_id == match.id,
            PvpRound.round_no == match.current_round,
            PvpRound.status == "open",
        )
        .one_or_none()
    )


def maybe_resolve_round(db: Session, match: PvpMatch) -> PvpRound | None:
    """若双方已选或已超时，则结算本轮（原子占位，避免双结算）。"""
    if match.status != "playing":
        return None
    rnd = current_open_round(db, match)
    if rnd is None:
        return None

    deadline = _as_utc(match.round_deadline)
    now = _as_utc(_now())
    timed_out = deadline is not None and now is not None and now >= deadline
    a_ready = rnd.choice_a is not None
    b_ready = rnd.choice_b is not None

    if not (a_ready and b_ready) and not timed_out:
        return None

    a_timed_out = bool(rnd.a_timed_out) or ((not a_ready) and timed_out)
    b_timed_out = bool(rnd.b_timed_out) or ((not b_ready) and timed_out)

    points_a, points_b = resolve_pvp_payoff(
        rnd.choice_a,
        rnd.choice_b,
        a_timed_out=a_timed_out,
        b_timed_out=b_timed_out,
    )

    # 仅当仍为 open 时写入 resolved，输掉竞态的请求直接退出
    claimed = db.execute(
        update(PvpRound)
        .where(PvpRound.id == rnd.id, PvpRound.status == "open")
        .values(
            status="resolved",
            a_timed_out=a_timed_out,
            b_timed_out=b_timed_out,
            points_a=points_a,
            points_b=points_b,
            resolved_at=_now(),
        )
    )
    if claimed.rowcount != 1:
        db.refresh(rnd)
        return None

    db.refresh(rnd)
    match.score_a += points_a
    match.score_b += points_b

    _mirror_round_to_sessions(db, match, rnd)

    if match.current_round >= match.rounds_total:
        _finish_match(db, match)
    else:
        match.current_round += 1
        start_round(db, match)
        for sid in (match.session_a_id, match.session_b_id):
            if not sid:
                continue
            sess = db.get(GameSession, sid)
            if sess and sess.status == "playing":
                sess.current_round = match.current_round
    db.flush()
    return rnd


def catch_up_match(db: Session, match: PvpMatch) -> None:
    """连续结算所有已到期的轮次（离线回来 / 扫尾用）。"""
    for _ in range(match.rounds_total + 2):
        if match.status != "playing":
            return
        if maybe_resolve_round(db, match) is None:
            return


def sweep_overdue_matches(db: Session, *, limit: int = 30) -> None:
    """扫一遍超时未结算的对局，避免双方都离线后永久卡死。"""
    now = _now()
    overdue = (
        db.query(PvpMatch)
        .filter(
            PvpMatch.status == "playing",
            PvpMatch.round_deadline.isnot(None),
            PvpMatch.round_deadline <= now,
        )
        .order_by(PvpMatch.id.asc())
        .limit(limit)
        .all()
    )
    for m in overdue:
        catch_up_match(db, m)


def claim_waiting_match(
    db: Session,
    *,
    scene_id: int,
    user_id: int,
) -> PvpMatch | None:
    """原子占座：把一条 waiting 改成 playing 并写入 user_b。失败返回 None。"""
    candidates = (
        db.query(PvpMatch.id)
        .filter(
            PvpMatch.status == "waiting",
            PvpMatch.scene_id == scene_id,
            PvpMatch.user_b_id.is_(None),
            PvpMatch.user_a_id != user_id,
        )
        .order_by(PvpMatch.id.asc())
        .limit(5)
        .all()
    )
    for (match_id,) in candidates:
        result = db.execute(
            update(PvpMatch)
            .where(
                PvpMatch.id == match_id,
                PvpMatch.status == "waiting",
                PvpMatch.user_b_id.is_(None),
            )
            .values(user_b_id=user_id, status="playing")
        )
        if result.rowcount == 1:
            db.flush()
            return db.get(PvpMatch, match_id)
    return None


def _mirror_round_to_sessions(db: Session, match: PvpMatch, rnd: PvpRound) -> None:
    """把本轮写入双方 GameSession，便于排行榜复用。"""
    # T means timeout/no choice. Never turn missing experimental data into B.
    choice_a = rnd.choice_a or "T"
    choice_b = rnd.choice_b or "T"
    if match.session_a_id:
        sa = db.get(GameSession, match.session_a_id)
        if sa and sa.status == "playing":
            db.add(
                GameRound(
                    session_id=sa.id,
                    round_no=rnd.round_no,
                    my_choice=choice_a,
                    opponent_choice=choice_b,
                    my_points=rnd.points_a or 0,
                    opponent_points=rnd.points_b or 0,
                )
            )
            sa.my_score = match.score_a
            sa.opponent_score = match.score_b
    if match.session_b_id:
        sb = db.get(GameSession, match.session_b_id)
        if sb and sb.status == "playing":
            db.add(
                GameRound(
                    session_id=sb.id,
                    round_no=rnd.round_no,
                    my_choice=choice_b,
                    opponent_choice=choice_a,
                    my_points=rnd.points_b or 0,
                    opponent_points=rnd.points_a or 0,
                )
            )
            sb.my_score = match.score_b
            sb.opponent_score = match.score_a


def _finish_match(db: Session, match: PvpMatch) -> None:
    match.status = "finished"
    match.finished_at = _now()
    match.round_deadline = None
    for sid in (match.session_a_id, match.session_b_id):
        if not sid:
            continue
        sess = db.get(GameSession, sid)
        if sess and sess.status == "playing":
            sess.status = "finished"
            sess.finished_at = match.finished_at
            sess.my_score = match.score_a if sid == match.session_a_id else match.score_b
            sess.opponent_score = match.score_b if sid == match.session_a_id else match.score_a


def create_sessions_for_match(
    db: Session,
    match: PvpMatch,
    scene: ExperimentScene,
    experiment: Experiment,
) -> None:
    assert match.user_b_id is not None
    sa = GameSession(
        user_id=match.user_a_id,
        experiment_id=experiment.id,
        scene_id=scene.id,
        mode="matched",
        bot_policy="pvp",
        bot_seed=0,
        status="playing",
        current_round=1,
    )
    sb = GameSession(
        user_id=match.user_b_id,
        experiment_id=experiment.id,
        scene_id=scene.id,
        mode="matched",
        bot_policy="pvp",
        bot_seed=0,
        status="playing",
        current_round=1,
    )
    db.add(sa)
    db.add(sb)
    db.flush()
    match.session_a_id = sa.id
    match.session_b_id = sb.id


def seat_of(match: PvpMatch, user_id: int) -> str | None:
    if match.user_a_id == user_id:
        return "a"
    if match.user_b_id == user_id:
        return "b"
    return None


class PvpRoundOut(BaseModel):
    round_no: int
    status: str
    my_choice: str | None = None
    opponent_choice: str | None = None
    my_points: int | None = None
    opponent_points: int | None = None
    my_timed_out: bool = False
    opponent_timed_out: bool = False


class PvpMatchOut(BaseModel):
    id: int
    status: str
    scene_key: str
    scene_title: str
    rounds_total: int
    current_round: int
    round_timeout_sec: int = PVP_ROUND_TIMEOUT_SEC
    round_deadline: datetime | None = None
    seconds_left: int | None = None
    my_score: int
    opponent_score: int
    opponent_nickname: str | None = None
    my_seat: str
    waiting: bool = False
    resumed: bool = False
    i_have_chosen: bool = False
    opponent_has_chosen: bool = False
    history: list[PvpRoundOut] = Field(default_factory=list)


def match_out(
    db: Session,
    match: PvpMatch,
    user: User,
    scene: ExperimentScene,
    *,
    resumed: bool = False,
) -> PvpMatchOut:
    catch_up_match(db, match)
    db.refresh(match)
    db.expire(match, ["rounds"])

    seat = seat_of(match, user.id)
    if seat is None:
        raise ValueError("not in match")

    opp_id = match.user_b_id if seat == "a" else match.user_a_id
    opp = db.get(User, opp_id) if opp_id else None
    my_score = match.score_a if seat == "a" else match.score_b
    opp_score = match.score_b if seat == "a" else match.score_a

    seconds_left = None
    deadline = _as_utc(match.round_deadline)
    if match.status == "playing" and deadline:
        seconds_left = max(0, int((deadline - _now()).total_seconds()))

    open_rnd = current_open_round(db, match)
    i_chosen = False
    opp_chosen = False
    if open_rnd:
        if seat == "a":
            i_chosen = open_rnd.choice_a is not None
            opp_chosen = open_rnd.choice_b is not None
        else:
            i_chosen = open_rnd.choice_b is not None
            opp_chosen = open_rnd.choice_a is not None

    history: list[PvpRoundOut] = []
    for r in sorted(match.rounds, key=lambda x: x.round_no):
        if r.status != "resolved":
            continue
        if seat == "a":
            history.append(
                PvpRoundOut(
                    round_no=r.round_no,
                    status=r.status,
                    my_choice=r.choice_a,
                    opponent_choice=r.choice_b,
                    my_points=r.points_a,
                    opponent_points=r.points_b,
                    my_timed_out=r.a_timed_out,
                    opponent_timed_out=r.b_timed_out,
                )
            )
        else:
            history.append(
                PvpRoundOut(
                    round_no=r.round_no,
                    status=r.status,
                    my_choice=r.choice_b,
                    opponent_choice=r.choice_a,
                    my_points=r.points_b,
                    opponent_points=r.points_a,
                    my_timed_out=r.b_timed_out,
                    opponent_timed_out=r.a_timed_out,
                )
            )

    return PvpMatchOut(
        id=match.id,
        status=match.status,
        scene_key=scene.scene_key,
        scene_title=scene.title,
        rounds_total=match.rounds_total,
        current_round=match.current_round,
        round_timeout_sec=PVP_ROUND_TIMEOUT_SEC,
        round_deadline=match.round_deadline,
        seconds_left=seconds_left,
        my_score=my_score,
        opponent_score=opp_score,
        opponent_nickname=opp.nickname if opp else None,
        my_seat=seat,
        waiting=match.status == "waiting",
        resumed=resumed,
        i_have_chosen=i_chosen,
        opponent_has_chosen=opp_chosen,
        history=history,
    )
