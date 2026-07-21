from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.data.bfi44_seed import INSTRUMENT_CODE
from app.data.stag_hunt_seed import STAG_HUNT_CODE
from app.models.game import Experiment, ExperimentScene, GameSession
from app.models.match import PvpDecisionTelemetry, PvpMatch
from app.models.survey import SurveyInstrument, SurveyResponse
from app.models.user import User
from app.services.pvp import (
    PvpMatchOut,
    catch_up_match,
    claim_waiting_match,
    create_sessions_for_match,
    current_open_round,
    match_out,
    maybe_resolve_round,
    seat_of,
    start_round,
    sweep_overdue_matches,
)
from app.services.game_comprehension import comprehension_passed

router = APIRouter(prefix="/api/v1/pvp", tags=["pvp"])


def _require_survey(db: Session, user: User) -> None:
    instrument = db.query(SurveyInstrument).filter(SurveyInstrument.code == INSTRUMENT_CODE).first()
    if instrument is None:
        raise HTTPException(status_code=403, detail="请先完成并提交 BFI-44 问卷")
    response = (
        db.query(SurveyResponse)
        .filter(
            SurveyResponse.user_id == user.id,
            SurveyResponse.instrument_id == instrument.id,
            SurveyResponse.status == "submitted",
        )
        .first()
    )
    if response is None:
        raise HTTPException(status_code=403, detail="请先完成并提交 BFI-44 问卷")
    if response.quality_passed is not True:
        raise HTTPException(status_code=403, detail="本次问卷未达到真人博弈的数据质量要求")


def _get_scene(db: Session, scene_key: str) -> tuple[Experiment, ExperimentScene]:
    experiment = (
        db.query(Experiment)
        .options(joinedload(Experiment.scenes))
        .filter(Experiment.code == STAG_HUNT_CODE)
        .first()
    )
    if experiment is None:
        raise HTTPException(status_code=500, detail="猎鹿博弈未初始化")
    if experiment.status != "active":
        raise HTTPException(status_code=403, detail="该实验当前未开放")
    scene = next((s for s in experiment.scenes if s.scene_key == scene_key and s.enabled), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="场景不存在或已停用")
    return experiment, scene


def _find_active(db: Session, user_id: int) -> PvpMatch | None:
    return (
        db.query(PvpMatch)
        .filter(
            PvpMatch.status.in_(["waiting", "playing"]),
            or_(PvpMatch.user_a_id == user_id, PvpMatch.user_b_id == user_id),
        )
        .order_by(PvpMatch.id.desc())
        .first()
    )


def _first_required_scene(experiment: Experiment) -> ExperimentScene | None:
    scenes = sorted(
        [scene for scene in experiment.scenes if scene.enabled and scene.required],
        key=lambda scene: (scene.sort_order, scene.id),
    )
    return scenes[0] if scenes else None


def _successor_for(db: Session, match: PvpMatch, user_id: int) -> PvpMatch | None:
    """Return the next scene automatically created for this fixed pair."""
    active = _find_active(db, user_id)
    if active is None or active.id == match.id:
        return None
    return active


@router.post("/stag-hunt/scenes/{scene_key}/queue", response_model=PvpMatchOut, status_code=201)
def join_queue(
    scene_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """加入唯一一次真人配对；两个必做场景均由同一对手连续完成。"""
    _require_survey(db, current_user)
    experiment, scene = _get_scene(db, scene_key)
    if not comprehension_passed(db, current_user.id, experiment.id):
        raise HTTPException(status_code=403, detail="请先通过猎鹿博弈规则理解检查")

    sweep_overdue_matches(db)
    active = _find_active(db, current_user.id)
    if active:
        catch_up_match(db, active)
        db.refresh(active)
        if active.status in ("waiting", "playing"):
            active_scene = db.get(ExperimentScene, active.scene_id)
            if active_scene is None:
                raise HTTPException(status_code=404, detail="场景不存在")
            out = match_out(db, active, current_user, active_scene, resumed=True)
            db.commit()
            return out

    paired_before = (
        db.query(PvpMatch.id)
        .filter(
            PvpMatch.experiment_id == experiment.id,
            PvpMatch.user_b_id.isnot(None),
            or_(PvpMatch.user_a_id == current_user.id, PvpMatch.user_b_id == current_user.id),
        )
        .first()
    )
    legacy_matched_session = (
        db.query(GameSession.id)
        .filter(
            GameSession.user_id == current_user.id,
            GameSession.experiment_id == experiment.id,
            GameSession.mode == "matched",
        )
        .first()
    )
    if paired_before is not None or legacy_matched_session is not None:
        raise HTTPException(
            status_code=409,
            detail="每位玩家只能参加一次正式实验，你已使用真人匹配资格",
        )

    first_scene = _first_required_scene(experiment)
    if first_scene is None:
        raise HTTPException(status_code=500, detail="正式实验尚未配置必做场景")
    if scene.id != first_scene.id:
        raise HTTPException(status_code=409, detail="正式实验必须从第一个场景开始")

    claimed = claim_waiting_match(db, scene_id=scene.id, user_id=current_user.id)
    if claimed:
        claimed.rounds_total = experiment.rounds_per_scene
        claimed.current_round = 1
        create_sessions_for_match(db, claimed, scene, experiment)
        start_round(db, claimed)
        db.commit()
        db.refresh(claimed)
        return match_out(db, claimed, current_user, scene)

    match = PvpMatch(
        experiment_id=experiment.id,
        scene_id=scene.id,
        status="waiting",
        user_a_id=current_user.id,
        rounds_total=experiment.rounds_per_scene,
        current_round=1,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match_out(db, match, current_user, scene)


@router.post("/queue/cancel")
def cancel_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消等待中的匹配。若已开局则无法取消，返回当前对局信息。"""
    waiting = (
        db.query(PvpMatch)
        .filter(PvpMatch.status == "waiting", PvpMatch.user_a_id == current_user.id)
        .order_by(PvpMatch.id.desc())
        .first()
    )
    if waiting is not None:
        waiting.status = "cancelled"
        waiting.finished_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
        return {"ok": True, "cancelled": True, "status": "cancelled", "match_id": waiting.id}

    active = _find_active(db, current_user.id)
    if active and active.status == "playing":
        return {
            "ok": True,
            "cancelled": False,
            "status": "playing",
            "match_id": active.id,
            "detail": "已匹配成功，无法取消",
        }
    return {"ok": True, "cancelled": False, "status": None, "match_id": None}


@router.get("/matches/{match_id}", response_model=PvpMatchOut)
def get_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    match = db.get(PvpMatch, match_id)
    if match is None or seat_of(match, current_user.id) is None:
        raise HTTPException(status_code=404, detail="对局不存在")
    scene = db.get(ExperimentScene, match.scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="场景不存在")
    catch_up_match(db, match)
    db.refresh(match)
    successor = _successor_for(db, match, current_user.id) if match.status == "finished" else None
    if successor is not None:
        next_scene = db.get(ExperimentScene, successor.scene_id)
        if next_scene is None:
            raise HTTPException(status_code=404, detail="下一实验场景不存在")
        out = match_out(db, successor, current_user, next_scene, resumed=True)
    else:
        out = match_out(db, match, current_user, scene)
    db.commit()
    return out


class PvpChoiceBody(BaseModel):
    choice: str = Field(pattern="^[ABab]$")
    # 可选：客户端声明要提交的轮次，防止超时后串轮
    round_no: int | None = None


@router.post("/matches/{match_id}/choice", response_model=PvpMatchOut)
def submit_choice(
    match_id: int,
    body: PvpChoiceBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    match = db.get(PvpMatch, match_id)
    if match is None or seat_of(match, current_user.id) is None:
        raise HTTPException(status_code=404, detail="对局不存在")
    if match.status != "playing":
        successor = _successor_for(db, match, current_user.id)
        if successor is not None:
            next_scene = db.get(ExperimentScene, successor.scene_id)
            if next_scene is None:
                raise HTTPException(status_code=404, detail="下一实验场景不存在")
            return match_out(db, successor, current_user, next_scene, resumed=True)
        raise HTTPException(status_code=400, detail="对局已结束或尚未开始")
    scene = db.get(ExperimentScene, match.scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="场景不存在")

    expected_round = body.round_no if body.round_no is not None else match.current_round
    open_before = current_open_round(db, match)
    open_before_id = open_before.id if open_before else None

    # 先结算超时；若因此进入下一轮，禁止把本次选择写入新轮
    maybe_resolve_round(db, match)
    db.refresh(match)

    if match.status != "playing":
        db.commit()
        successor = _successor_for(db, match, current_user.id)
        if successor is not None:
            next_scene = db.get(ExperimentScene, successor.scene_id)
            if next_scene is None:
                raise HTTPException(status_code=404, detail="下一实验场景不存在")
            return match_out(db, successor, current_user, next_scene, resumed=True)
        raise HTTPException(status_code=400, detail="对局已结束或尚未开始")

    if match.current_round != expected_round:
        db.commit()
        raise HTTPException(status_code=409, detail="本轮已超时结算，请在新一轮重新选择")

    rnd = current_open_round(db, match)
    if rnd is None or (open_before_id is not None and rnd.id != open_before_id):
        db.commit()
        raise HTTPException(status_code=409, detail="本轮已结束，请刷新后重试")

    seat = seat_of(match, current_user.id)
    choice = body.choice.upper()
    now = datetime.now(UTC).replace(tzinfo=None)
    started_at = rnd.started_at
    if started_at.tzinfo is not None:
        started_at = started_at.astimezone(UTC).replace(tzinfo=None)
    decision_ms = max(0, int((now - started_at).total_seconds() * 1000))
    if seat == "a":
        if rnd.choice_a is not None:
            db.commit()
            raise HTTPException(status_code=400, detail="本轮已提交过选择")
        rnd.choice_a = choice
    else:
        if rnd.choice_b is not None:
            db.commit()
            raise HTTPException(status_code=400, detail="本轮已提交过选择")
        rnd.choice_b = choice

    db.add(
        PvpDecisionTelemetry(
            match_id=match.id,
            round_no=rnd.round_no,
            user_id=current_user.id,
            decision_ms=decision_ms,
            submitted_at=now,
        )
    )

    maybe_resolve_round(db, match)
    db.commit()
    db.refresh(match)
    successor = _successor_for(db, match, current_user.id) if match.status == "finished" else None
    if successor is not None:
        next_scene = db.get(ExperimentScene, successor.scene_id)
        if next_scene is None:
            raise HTTPException(status_code=404, detail="下一实验场景不存在")
        return match_out(db, successor, current_user, next_scene)
    return match_out(db, match, current_user, scene)
