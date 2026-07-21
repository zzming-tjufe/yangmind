import random
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.data.bfi44_seed import INSTRUMENT_CODE
from app.data.stag_hunt_seed import ROUNDS_PER_SCENE, STAG_HUNT_CODE
from app.models.game import Experiment, ExperimentScene, GameRound, GameSession
from app.models.match import PvpMatch
from app.models.survey import SurveyInstrument, SurveyResponse
from app.models.user import User
from app.schemas.game import (
    ComprehensionOut,
    ComprehensionSubmitRequest,
    PlayRoundRequest,
    RoundOut,
    SceneOut,
    SessionOut,
    StagHuntProgressOut,
)
from app.services.game_comprehension import (
    COMPREHENSION_QUESTIONS,
    CORRECT_ANSWERS,
    comprehension_passed,
    get_comprehension,
    submit_comprehension,
)
from app.services.game_engine import bot_choice, calc_payoff

router = APIRouter(prefix="/api/v1", tags=["games"])


def _submitted_survey(db: Session, user_id: int) -> SurveyResponse | None:
    instrument = db.query(SurveyInstrument).filter(SurveyInstrument.code == INSTRUMENT_CODE).first()
    if instrument is None:
        return None
    return (
        db.query(SurveyResponse)
        .filter(
            SurveyResponse.user_id == user_id,
            SurveyResponse.instrument_id == instrument.id,
            SurveyResponse.status == "submitted",
        )
        .first()
    )


def _survey_submitted(db: Session, user_id: int) -> bool:
    return _submitted_survey(db, user_id) is not None


def _require_survey(db: Session, user: User) -> None:
    response = _submitted_survey(db, user.id)
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成并提交 BFI-44 问卷，再进入博弈",
        )
    if response.quality_passed is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="本次问卷未达到真人博弈的数据质量要求",
        )


def _get_stag_experiment(db: Session) -> Experiment:
    experiment = (
        db.query(Experiment)
        .options(joinedload(Experiment.scenes))
        .filter(Experiment.code == STAG_HUNT_CODE)
        .first()
    )
    if experiment is None:
        raise HTTPException(status_code=500, detail="猎鹿博弈未初始化，请重启后端")
    return experiment


def _require_active_experiment(experiment: Experiment) -> None:
    if experiment.status != "active":
        raise HTTPException(status_code=403, detail="该实验当前未开放")


def _finished_scene_keys(db: Session, user_id: int, experiment_id: int) -> dict[int, int]:
    """scene_id -> 该场景已完成真人局的最高得分。"""
    rows = (
        db.query(GameSession)
        .filter(
            GameSession.user_id == user_id,
            GameSession.experiment_id == experiment_id,
            GameSession.mode == "matched",
            GameSession.status == "finished",
        )
        .all()
    )
    best: dict[int, int] = {}
    for s in rows:
        best[s.scene_id] = max(best.get(s.scene_id, 0), s.my_score)
    return best


def _progress_flags(db: Session, user: User, experiment: Experiment) -> tuple[int, int, bool]:
    best = _finished_scene_keys(db, user.id, experiment.id)
    required_scene_ids = {
        scene.id for scene in experiment.scenes if scene.enabled and scene.required
    }
    done = len(required_scene_ids.intersection(best))
    required = len(required_scene_ids)
    return done, required, required > 0 and done == required


def _session_out(db: Session, session: GameSession, user: User) -> SessionOut:
    experiment = db.get(Experiment, session.experiment_id)
    scene = db.get(ExperimentScene, session.scene_id)
    history = [
        RoundOut.model_validate(r)
        for r in sorted(session.rounds, key=lambda x: x.round_no)
    ]
    last = history[-1] if history else None
    _, _, all_done = _progress_flags(db, user, experiment) if experiment else (0, 0, False)
    return SessionOut(
        id=session.id,
        scene_key=scene.scene_key if scene else "",
        status=session.status,
        current_round=session.current_round,
        rounds_total=experiment.rounds_per_scene if experiment else ROUNDS_PER_SCENE,
        my_score=session.my_score,
        opponent_score=session.opponent_score,
        last_round=last,
        history=history,
        experiment_all_done=all_done if session.status == "finished" else False,
    )


@router.get("/experiments/stag-hunt/scenes", response_model=StagHuntProgressOut)
def list_stag_scenes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """场景列表 + 个人完成进度。"""
    experiment = _get_stag_experiment(db)
    survey_response = _submitted_survey(db, current_user.id)
    survey_done = survey_response is not None
    survey_quality_failed = survey_done and survey_response.quality_passed is not True
    unlocked = survey_done and not survey_quality_failed and experiment.status == "active"
    understood = comprehension_passed(db, current_user.id, experiment.id)
    best = _finished_scene_keys(db, current_user.id, experiment.id)
    scenes_sorted = sorted(
        [s for s in experiment.scenes if s.enabled],
        key=lambda x: x.sort_order,
    )
    required_scene_ids = {scene.id for scene in scenes_sorted if scene.required}
    done = len(required_scene_ids.intersection(best))
    required = len(required_scene_ids)
    all_done = required > 0 and done == required

    active_match = (
        db.query(PvpMatch)
        .filter(
            PvpMatch.experiment_id == experiment.id,
            PvpMatch.status.in_(("waiting", "playing")),
            or_(
                PvpMatch.user_a_id == current_user.id,
                PvpMatch.user_b_id == current_user.id,
            ),
        )
        .order_by(PvpMatch.id.desc())
        .first()
    )
    paired_match_exists = (
        db.query(PvpMatch.id)
        .filter(
            PvpMatch.experiment_id == experiment.id,
            PvpMatch.user_b_id.isnot(None),
            or_(
                PvpMatch.user_a_id == current_user.id,
                PvpMatch.user_b_id == current_user.id,
            ),
        )
        .first()
        is not None
    )
    legacy_matched_session_exists = (
        db.query(GameSession.id)
        .filter(
            GameSession.user_id == current_user.id,
            GameSession.experiment_id == experiment.id,
            GameSession.mode == "matched",
        )
        .first()
        is not None
    )
    participation_locked = paired_match_exists or legacy_matched_session_exists

    return StagHuntProgressOut(
        experiment_code=experiment.code,
        title=experiment.title,
        rounds_per_scene=experiment.rounds_per_scene,
        unlock_games=unlocked,
        survey_done=survey_done,
        survey_quality_failed=survey_quality_failed,
        comprehension_passed=understood,
        experiment_status=experiment.status,
        done_count=done,
        required_count=required,
        all_done=all_done,
        participation_locked=participation_locked,
        active_match_id=active_match.id if active_match is not None else None,
        scenes=[
            SceneOut(
                scene_key=s.scene_key,
                no=s.no,
                title=s.title,
                short_desc=s.short_desc,
                option_a=s.option_a,
                option_b=s.option_b,
                option_a_text=s.option_a_text,
                option_b_text=s.option_b_text,
                required=s.required,
                completed=s.id in best,
                best_score=best.get(s.id),
            )
            for s in scenes_sorted
        ],
    )


def _comprehension_out(db: Session, user_id: int, experiment_id: int) -> ComprehensionOut:
    row = get_comprehension(db, user_id, experiment_id)
    return ComprehensionOut(
        passed=bool(row and row.passed),
        attempts=row.attempts if row else 0,
        incorrect_ids=list(row.last_incorrect_ids or []) if row else [],
        questions=COMPREHENSION_QUESTIONS,
    )


@router.get(
    "/experiments/stag-hunt/comprehension",
    response_model=ComprehensionOut,
)
def get_stag_comprehension(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取真人匹配前的规则理解检查。"""
    _require_survey(db, current_user)
    experiment = _get_stag_experiment(db)
    _require_active_experiment(experiment)
    return _comprehension_out(db, current_user.id, experiment.id)


@router.post(
    "/experiments/stag-hunt/comprehension",
    response_model=ComprehensionOut,
)
def check_stag_comprehension(
    body: ComprehensionSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """全部答对后记录通过；答错可复习规则并再次检查。"""
    _require_survey(db, current_user)
    experiment = _get_stag_experiment(db)
    _require_active_experiment(experiment)
    expected_ids = set(CORRECT_ANSWERS)
    if set(body.answers) != expected_ids:
        raise HTTPException(status_code=400, detail="请完成全部理解检查题")
    row = submit_comprehension(db, current_user.id, experiment.id, body.answers)
    return _comprehension_out(db, current_user.id, experiment.id)


@router.post(
    "/experiments/stag-hunt/scenes/{scene_key}/sessions",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
)
def start_session(
    scene_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """开始一局猎鹿博弈（机器人对手）。"""
    _require_survey(db, current_user)
    experiment = _get_stag_experiment(db)
    _require_active_experiment(experiment)
    if not comprehension_passed(db, current_user.id, experiment.id):
        raise HTTPException(status_code=403, detail="请先通过猎鹿博弈规则理解检查")
    scene = next((s for s in experiment.scenes if s.scene_key == scene_key and s.enabled), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 若有进行中的同场景对局，直接返回（避免重复开很多局）
    playing = (
        db.query(GameSession)
        .options(joinedload(GameSession.rounds))
        .filter(
            GameSession.user_id == current_user.id,
            GameSession.scene_id == scene.id,
            GameSession.status == "playing",
        )
        .order_by(GameSession.id.desc())
        .first()
    )
    if playing:
        return _session_out(db, playing, current_user)

    session = GameSession(
        user_id=current_user.id,
        experiment_id=experiment.id,
        scene_id=scene.id,
        mode="bot",
        bot_policy="coop_0.64",
        bot_seed=random.randint(1, 2_000_000_000),
        status="playing",
        current_round=1,
        my_score=0,
        opponent_score=0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    session = (
        db.query(GameSession)
        .options(joinedload(GameSession.rounds))
        .filter(GameSession.id == session.id)
        .one()
    )
    return _session_out(db, session, current_user)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(GameSession)
        .options(joinedload(GameSession.rounds))
        .filter(GameSession.id == session_id, GameSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="对局不存在")
    return _session_out(db, session, current_user)


@router.post("/sessions/{session_id}/rounds", response_model=SessionOut)
def play_round(
    session_id: int,
    body: PlayRoundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交本轮选择；对方由服务端生成，分数由服务端计算。"""
    session = (
        db.query(GameSession)
        .options(joinedload(GameSession.rounds))
        .filter(GameSession.id == session_id, GameSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="对局不存在")
    if session.status != "playing":
        raise HTTPException(status_code=400, detail="本局已结束，不能再答题")

    experiment = db.get(Experiment, session.experiment_id)
    total = experiment.rounds_per_scene if experiment else ROUNDS_PER_SCENE
    if len(session.rounds) >= total:
        raise HTTPException(status_code=400, detail="轮次已满")

    round_no = session.current_round
    if any(r.round_no == round_no for r in session.rounds):
        raise HTTPException(status_code=400, detail="本轮已提交过")

    mine = body.choice.upper()
    theirs = bot_choice(session.bot_seed, round_no)
    my_points, their_points = calc_payoff(mine, theirs)

    db.add(
        GameRound(
            session_id=session.id,
            round_no=round_no,
            my_choice=mine,
            opponent_choice=theirs,
            my_points=my_points,
            opponent_points=their_points,
        )
    )
    session.my_score += my_points
    session.opponent_score += their_points

    if round_no >= total:
        session.status = "finished"
        session.finished_at = datetime.now(UTC)
    else:
        session.current_round = round_no + 1

    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="本轮已提交或正在处理，请刷新对局状态",
        ) from None
    session = (
        db.query(GameSession)
        .options(joinedload(GameSession.rounds))
        .filter(GameSession.id == session.id)
        .one()
    )
    return _session_out(db, session, current_user)


@router.post("/sessions/{session_id}/abandon", response_model=SessionOut)
def abandon_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(GameSession)
        .options(joinedload(GameSession.rounds))
        .filter(GameSession.id == session_id, GameSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="对局不存在")
    if session.status == "playing":
        session.status = "abandoned"
        session.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(session)
    return _session_out(db, session, current_user)
