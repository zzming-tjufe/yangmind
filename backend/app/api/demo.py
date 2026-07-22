"""管理员演示模式 API：内存计算，不写正式业务表。"""

from __future__ import annotations

import random
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.data.stag_hunt_seed import ROUNDS_PER_SCENE, STAG_HUNT_CODE
from app.models.game import Experiment
from app.models.survey import SurveyInstrument, SurveyItem
from app.models.user import User
from app.schemas.survey import AnswerItem, AttentionAnswer, DiligenceAnswer, SaveAnswersRequest
from app.services.bfi_scoring import (
    ATTENTION_CHECKS,
    build_summary_label,
    check_quality,
    compute_dimension_scores,
)
from app.services.demo_store import DemoRound, DemoSession, get_store, reset_store
from app.services.game_engine import calc_payoff, demo_bot_choice
from app.data.bfi44_seed import INSTRUMENT_CODE

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class DemoSurveySubmitBody(BaseModel):
    answers: list[AnswerItem] = Field(min_length=44, max_length=44)
    attention_answers: list[AttentionAnswer] = Field(min_length=2, max_length=2)
    diligence_answers: list[DiligenceAnswer] = Field(min_length=3, max_length=3)


class DemoPlayRoundBody(BaseModel):
    choice: str = Field(pattern="^(A|B|a|b)$")


def _survey_out(store) -> dict[str, Any]:
    s = store.survey
    return {
        "status": s.status if s.status != "none" else "none",
        "answered_count": len(s.answers),
        "answers": {str(k): v for k, v in s.answers.items()},
        "personality": s.personality,
        "quality_passed": s.quality_passed,
        "unlock_games": s.status == "submitted",
        "feedback_unlocked": s.status == "submitted" and s.personality is not None,
        "demo": True,
    }


def _session_as_pvp(session: DemoSession) -> dict[str, Any]:
    history = [
        {
            "round_no": r.round_no,
            "status": "settled",
            "my_choice": r.my_choice,
            "opponent_choice": r.opponent_choice,
            "my_points": r.my_points,
            "opponent_points": r.opponent_points,
            "my_timed_out": False,
            "opponent_timed_out": False,
        }
        for r in session.history
    ]
    return {
        "id": session.id,
        "status": session.status,
        "scene_key": session.scene_key,
        "scene_title": session.scene_title,
        "rounds_total": session.rounds_total,
        "current_round": session.current_round,
        "round_timeout_sec": 999,
        "round_deadline": None,
        "seconds_left": 999 if session.status == "playing" else 0,
        "my_score": session.my_score,
        "opponent_score": session.opponent_score,
        "opponent_nickname": "演示机器人",
        "opponent_has_chosen": False,
        "i_have_chosen": False,
        "my_choice": None,
        "history": history,
        "resumed": False,
        "demo": True,
        "mode": "bot_demo",
    }


@router.post("/reset")
def demo_reset(admin: User = Depends(get_current_admin)):
    reset_store(admin.id)
    return {"ok": True, "demo": True}


@router.get("/surveys/bfi-44/my-response")
def demo_my_response(admin: User = Depends(get_current_admin)):
    return _survey_out(get_store(admin.id))


@router.put("/surveys/bfi-44/answers")
def demo_save_answers(
    body: SaveAnswersRequest,
    admin: User = Depends(get_current_admin),
):
    """演示草稿仅存内存；已提交后再次保存会重置为可重做演示。"""
    store = get_store(admin.id)
    if store.survey.status == "submitted":
        store.survey.status = "in_progress"
        store.survey.personality = None
        store.survey.quality_passed = None
        store.survey.quality_flags = None
    if store.survey.status == "none":
        store.survey.status = "in_progress"
    for a in body.answers:
        store.survey.answers[a.item_no] = a.value
    return _survey_out(store)


@router.post("/surveys/bfi-44/submit")
def demo_submit(
    body: DemoSurveySubmitBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    instrument = db.query(SurveyInstrument).filter(SurveyInstrument.code == INSTRUMENT_CODE).first()
    if instrument is None:
        raise HTTPException(status_code=500, detail="题库未初始化")

    amap = {a.item_no: a.value for a in body.answers}
    if len(amap) != 44 or any(i not in amap for i in range(1, 45)):
        raise HTTPException(status_code=400, detail="请完成全部 44 题后再提交")

    items_meta = (
        db.query(SurveyItem)
        .filter(SurveyItem.instrument_id == instrument.id)
        .order_by(SurveyItem.item_no)
        .all()
    )
    meta = [(i.item_no, i.dimension, i.reverse_scored) for i in items_meta]
    scores = compute_dimension_scores(amap, meta)
    attention = {a.check_id: a.value for a in body.attention_answers}
    allowed = {c["check_id"] for c in ATTENTION_CHECKS}
    if set(attention) != allowed:
        raise HTTPException(status_code=400, detail="请完成全部作答确认题")
    passed, flags = check_quality(amap, duration_seconds=300, attention_answers=attention)
    summary = build_summary_label(scores)

    store = get_store(admin.id)
    store.survey.answers = amap
    store.survey.status = "submitted"
    store.survey.quality_passed = passed
    store.survey.quality_flags = flags
    store.survey.personality = {
        "e": scores["E"],
        "a": scores["A"],
        "c": scores["C"],
        "n": scores["N"],
        "o": scores["O"],
        "summary_label": summary,
    }
    # 演示：提交后即可看人格，不要求先打完博弈
    return _survey_out(store)


@router.get("/stag-hunt/scenes")
def demo_scenes(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    store = get_store(admin.id)
    experiment = (
        db.query(Experiment)
        .options(joinedload(Experiment.scenes))
        .filter(Experiment.code == STAG_HUNT_CODE)
        .first()
    )
    if experiment is None:
        raise HTTPException(status_code=500, detail="猎鹿博弈未初始化")

    scenes = []
    for s in sorted(
        experiment.scenes,
        key=lambda x: (getattr(x, "sort_order", None) or x.id),
    ):
        if not s.enabled:
            continue
        scenes.append(
            {
                "scene_key": s.scene_key,
                "no": getattr(s, "no", None) or str(getattr(s, "sort_order", None) or s.id),
                "title": s.title,
                "short_desc": s.short_desc or "",
                "option_a": s.option_a,
                "option_b": s.option_b,
                "option_a_text": s.option_a_text or "",
                "option_b_text": s.option_b_text or "",
                "required": bool(s.required),
                "completed": s.scene_key in store.completed_scenes,
                "best_score": None,
            }
        )
    required = [s for s in scenes if s["required"]]
    done = sum(1 for s in required if s["completed"])
    survey_done = store.survey.status == "submitted"
    return {
        "experiment_code": experiment.code,
        "title": experiment.title,
        "rounds_per_scene": experiment.rounds_per_scene or ROUNDS_PER_SCENE,
        "unlock_games": survey_done,
        "survey_done": survey_done,
        "survey_quality_failed": False,
        "comprehension_passed": True,
        "experiment_status": "active",
        "done_count": done,
        "required_count": len(required),
        "all_done": len(required) > 0 and done >= len(required),
        "participation_locked": False,
        "active_match_id": None,
        "scenes": scenes,
        "payoff_matrix": {
            "AA": "10 / 10",
            "AB": "0 / 6",
            "BA": "6 / 0",
            "BB": "6 / 6",
        },
        "demo": True,
    }


@router.post("/stag-hunt/scenes/{scene_key}/sessions")
def demo_start_session(
    scene_key: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    store = get_store(admin.id)
    if store.survey.status != "submitted":
        raise HTTPException(status_code=403, detail="请先在演示模式中提交问卷")

    experiment = (
        db.query(Experiment)
        .options(joinedload(Experiment.scenes))
        .filter(Experiment.code == STAG_HUNT_CODE)
        .first()
    )
    if experiment is None:
        raise HTTPException(status_code=500, detail="猎鹿博弈未初始化")
    scene = next((s for s in experiment.scenes if s.scene_key == scene_key and s.enabled), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="场景不存在")

    sid = store.next_session_id
    store.next_session_id += 1
    session = DemoSession(
        id=sid,
        scene_key=scene.scene_key,
        scene_title=scene.title,
        rounds_total=experiment.rounds_per_scene or ROUNDS_PER_SCENE,
        rng_seed=random.randint(1, 2_000_000_000),
    )
    store.sessions[sid] = session
    return _session_as_pvp(session)


@router.post("/sessions/{session_id}/rounds")
def demo_play_round(
    session_id: int,
    body: DemoPlayRoundBody,
    admin: User = Depends(get_current_admin),
):
    store = get_store(admin.id)
    session = store.sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="演示对局不存在")
    if session.status != "playing":
        raise HTTPException(status_code=400, detail="本局已结束")
    if len(session.history) >= session.rounds_total:
        raise HTTPException(status_code=400, detail="轮次已满")

    round_no = session.current_round
    mine = body.choice.upper()
    rng = random.Random(session.rng_seed + round_no * 10007)
    theirs = demo_bot_choice(rng, bias_rate=0.6)
    my_pts, their_pts = calc_payoff(mine, theirs)
    rnd = DemoRound(
        round_no=round_no,
        my_choice=mine,
        opponent_choice=theirs,
        my_points=my_pts,
        opponent_points=their_pts,
    )
    session.history.append(rnd)
    session.my_score += my_pts
    session.opponent_score += their_pts

    if len(session.history) >= session.rounds_total:
        session.status = "finished"
        store.completed_scenes.add(session.scene_key)
    else:
        session.current_round = round_no + 1

    return _session_as_pvp(session)
