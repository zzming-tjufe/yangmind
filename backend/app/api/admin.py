from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_admin, get_current_super_admin
from app.core.database import get_db
from app.core.roles import (
    INVITE_KIND_PARTICIPANT,
    INVITE_KIND_SUB,
    INVITE_KINDS,
    ROLE_SUB,
    is_sudo,
    is_super_admin,
)
from app.core.security import hash_password
from app.data.personality_meta import PERSONALITY_META, personality_band
from app.models.admin_extra import AccountEvent, InviteCode
from app.models.cms import Announcement, ContentBlock, PageConfig
from app.models.game import Experiment, ExperimentScene, GameSession
from app.models.match import PvpMatch
from app.models.survey import (
    PersonalityScore,
    SurveyAnswer,
    SurveyQualityTelemetry,
    SurveyResponse,
    SurveyRetakeArchive,
)
from app.models.user import User
from app.schemas.admin import (
    AdminPersonalityOut,
    AdminStatsOut,
    AdminUserRow,
    AdminUsersOut,
    DimensionDetail,
)
from app.services.rbac_scope import (
    assert_can_manage_participant,
    assert_can_manage_sub_admin,
    list_sub_admins,
    participant_query_for_staff,
)
from app.services.admin_export import export_dataset
from app.services.app_version import (
    APP_VERSION_BLOCK_KEY,
    get_app_display_version,
    set_app_display_version,
)
from app.services.stats import (
    admin_overview_stats,
    latest_personality,
    survey_quality_passed_for_user,
    survey_status_for_user,
    user_game_stats,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _log_event(
    db: Session,
    *,
    event_type: str,
    detail: str = "",
    user_id: int | None = None,
    actor_id: int | None = None,
) -> None:
    db.add(
        AccountEvent(
            user_id=user_id,
            actor_id=actor_id,
            event_type=event_type,
            detail=detail,
        )
    )


def _survey_retake_state(db: Session, user_id: int) -> tuple[bool, int, str | None]:
    response = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.user_id == user_id)
        .order_by(SurveyResponse.id.desc())
        .first()
    )
    retake_count = (
        db.query(SurveyRetakeArchive)
        .filter(SurveyRetakeArchive.user_id == user_id)
        .count()
    )
    if response is None or response.status != "submitted":
        return False, retake_count, "用户尚未正式提交问卷"
    has_session = db.query(GameSession.id).filter(GameSession.user_id == user_id).first()
    has_match = (
        db.query(PvpMatch.id)
        .filter(or_(PvpMatch.user_a_id == user_id, PvpMatch.user_b_id == user_id))
        .first()
    )
    if has_session or has_match:
        return False, retake_count, "用户已进入博弈，为避免污染前测数据不能重做"
    return True, retake_count, None


# ---------- 概览 / 用户 ----------


@router.get("/stats/overview", response_model=AdminStatsOut)
def stats_overview(db: Session = Depends(get_db), _: User = Depends(get_current_super_admin)):
    return AdminStatsOut(**admin_overview_stats(db))


@router.get("/users", response_model=AdminUsersOut)
def list_users(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    query = participant_query_for_staff(db, admin)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((User.nickname.like(like)) | (User.public_id.like(like)) | (User.email.like(like)))
    users = query.order_by(User.id.desc()).all()
    return AdminUsersOut(total=len(users), items=_build_admin_user_rows(db, users))


def _build_admin_user_rows(db: Session, users: list[User]) -> list[AdminUserRow]:
    """批量组装用户列表，避免逐用户 N+1 查询。"""
    if not users:
        return []

    user_ids = [u.id for u in users]

    game_rows = (
        db.query(
            GameSession.user_id,
            func.coalesce(func.sum(GameSession.my_score), 0),
            func.count(GameSession.id),
        )
        .filter(GameSession.user_id.in_(user_ids), GameSession.status == "finished")
        .group_by(GameSession.user_id)
        .all()
    )
    game_map = {uid: (int(total or 0), int(cnt or 0)) for uid, total, cnt in game_rows}

    personality_map: dict[int, PersonalityScore] = {}
    for row in (
        db.query(PersonalityScore)
        .filter(PersonalityScore.user_id.in_(user_ids))
        .order_by(PersonalityScore.id.desc())
        .all()
    ):
        if row.user_id not in personality_map:
            personality_map[row.user_id] = row

    responses = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.user_id.in_(user_ids))
        .order_by(SurveyResponse.id.desc())
        .all()
    )
    latest_submitted: dict[int, SurveyResponse] = {}
    in_progress_users: set[int] = set()
    for resp in responses:
        if resp.status == "submitted" and resp.user_id not in latest_submitted:
            latest_submitted[resp.user_id] = resp
        elif resp.status == "in_progress":
            in_progress_users.add(resp.user_id)

    submitted_ids = [r.id for r in latest_submitted.values()]
    telemetry_map: dict[int, SurveyQualityTelemetry] = {}
    if submitted_ids:
        for tele in (
            db.query(SurveyQualityTelemetry)
            .filter(SurveyQualityTelemetry.response_id.in_(submitted_ids))
            .all()
        ):
            telemetry_map[tele.response_id] = tele

    retake_map = {
        uid: int(cnt)
        for uid, cnt in (
            db.query(SurveyRetakeArchive.user_id, func.count(SurveyRetakeArchive.id))
            .filter(SurveyRetakeArchive.user_id.in_(user_ids))
            .group_by(SurveyRetakeArchive.user_id)
            .all()
        )
    }

    session_users = {
        uid
        for (uid,) in db.query(GameSession.user_id)
        .filter(GameSession.user_id.in_(user_ids))
        .distinct()
        .all()
    }
    pvp_users = {
        uid
        for (uid,) in db.query(PvpMatch.user_a_id).filter(PvpMatch.user_a_id.in_(user_ids)).distinct().all()
    } | {
        uid
        for (uid,) in db.query(PvpMatch.user_b_id).filter(PvpMatch.user_b_id.in_(user_ids)).distinct().all()
    }

    items: list[AdminUserRow] = []
    for u in users:
        total, sessions = game_map.get(u.id, (0, 0))
        personality = personality_map.get(u.id)
        submitted = latest_submitted.get(u.id)
        if submitted is None:
            survey_status = "作答中" if u.id in in_progress_users else "未完成"
            quality_passed = None
        elif submitted.quality_passed is False:
            survey_status = "质量未过"
            quality_passed = False
        else:
            survey_status = "已完成"
            quality_passed = submitted.quality_passed

        retake_count = retake_map.get(u.id, 0)
        if submitted is None:
            can_retake, retake_block_reason = False, "用户尚未正式提交问卷"
        elif u.id in session_users or u.id in pvp_users:
            can_retake, retake_block_reason = False, "用户已进入博弈，为避免污染前测数据不能重做"
        else:
            can_retake, retake_block_reason = True, None

        quality_telemetry = telemetry_map.get(submitted.id) if submitted else None
        items.append(
            AdminUserRow(
                id=u.id,
                nickname=u.nickname,
                public_id=u.public_id,
                email=u.email,
                role=u.role,
                total_score=total,
                sessions_count=sessions,
                personality_summary=personality.summary_label if personality else "待生成",
                survey_status=survey_status,
                quality_passed=quality_passed,
                has_personality=personality is not None,
                status=u.status,
                can_retake_survey=can_retake,
                retake_count=retake_count,
                retake_block_reason=retake_block_reason,
                has_submitted_survey=submitted is not None,
                quality_review_status=(quality_telemetry.admin_review_status if quality_telemetry else None),
                quality_soft_flags=list(quality_telemetry.soft_flags or []) if quality_telemetry else [],
                quality_hard_exclusion=bool(quality_telemetry and quality_telemetry.hard_exclusion),
                is_debug=bool(getattr(u, "is_debug", False)),
            )
        )
    return items


class UserStatusBody(BaseModel):
    status: str = Field(pattern="^(active|disabled)$")


@router.patch("/users/{user_id}/status")
def set_user_status(
    user_id: int,
    body: UserStatusBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = db.get(User, user_id)
    if user is not None and user.role == ROLE_SUB:
        assert_can_manage_sub_admin(admin, user)
    else:
        assert_can_manage_participant(db, admin, user)
    user.status = body.status
    status_label = "正常启用" if body.status == "active" else "已禁用"
    role_label = "子管理员" if user.role == ROLE_SUB else "员工"
    _log_event(
        db,
        event_type="admin_status_change",
        detail=f"将{role_label} {user.nickname}（{user.public_id}）设为{status_label}",
        user_id=user.id,
        actor_id=admin.id,
    )
    db.commit()
    return {"ok": True, "id": user.id, "status": user.status}


class ResetPasswordBody(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    body: ResetPasswordBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = db.get(User, user_id)
    assert_can_manage_participant(db, admin, user)
    # Access tokens are bound to this hash, so resetting it revokes all old tokens.
    user.password_hash = hash_password(body.new_password)
    _log_event(
        db,
        event_type="admin_reset_password",
        detail=f"重置了 {user.nickname}（{user.public_id}）的登录密码",
        user_id=user.id,
        actor_id=admin.id,
    )
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/allow-survey-retake")
def allow_survey_retake(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """管理员核实技术故障后授权重做；原答卷完整归档且禁止博弈后重测。"""
    user = db.get(User, user_id)
    assert_can_manage_participant(db, admin, user)
    can_retake, retake_count, block_reason = _survey_retake_state(db, user_id)
    if not can_retake:
        raise HTTPException(status_code=400, detail=block_reason or "当前不能授权重做")

    response = (
        db.query(SurveyResponse)
        .options(joinedload(SurveyResponse.answers), joinedload(SurveyResponse.personality_score))
        .filter(SurveyResponse.user_id == user_id, SurveyResponse.status == "submitted")
        .order_by(SurveyResponse.id.desc())
        .first()
    )
    if response is None:
        raise HTTPException(status_code=400, detail="用户尚未正式提交问卷")

    personality = response.personality_score
    telemetry = (
        db.query(SurveyQualityTelemetry)
        .filter(SurveyQualityTelemetry.response_id == response.id)
        .first()
    )
    snapshot = {
        "response": {
            "id": response.id,
            "instrument_version": response.instrument_version,
            "started_at": response.started_at.isoformat() if response.started_at else None,
            "submitted_at": response.submitted_at.isoformat() if response.submitted_at else None,
            "quality_flags": response.quality_flags,
            "quality_passed": response.quality_passed,
        },
        "answers": [
            {"item_no": answer.item_no, "value": answer.value}
            for answer in sorted(response.answers, key=lambda item: item.item_no)
        ],
        "personality": None
        if personality is None
        else {
            "e": personality.e,
            "a": personality.a,
            "c": personality.c,
            "n": personality.n,
            "o": personality.o,
            "summary_label": personality.summary_label,
        },
        "quality_telemetry": None
        if telemetry is None
        else {
            "attention_answers": telemetry.attention_answers,
            "diligence_answers": telemetry.diligence_answers,
            "page_timings_seconds": telemetry.page_timings_seconds,
            "blur_count": telemetry.blur_count,
            "hard_exclusion": telemetry.hard_exclusion,
            "hard_exclusion_reasons": telemetry.hard_exclusion_reasons,
            "soft_flags": telemetry.soft_flags,
            "admin_review_status": telemetry.admin_review_status,
            "admin_review_reason": telemetry.admin_review_reason,
        },
    }
    db.add(
        SurveyRetakeArchive(
            user_id=user_id,
            instrument_id=response.instrument_id,
            original_response_id=response.id,
            retake_no=retake_count + 1,
            authorized_by_user_id=admin.id,
            response_snapshot=snapshot,
        )
    )
    db.query(PersonalityScore).filter(PersonalityScore.response_id == response.id).delete(
        synchronize_session=False
    )
    db.query(SurveyAnswer).filter(SurveyAnswer.response_id == response.id).delete(
        synchronize_session=False
    )
    db.query(SurveyQualityTelemetry).filter(
        SurveyQualityTelemetry.response_id == response.id
    ).delete(synchronize_session=False)
    response.status = "in_progress"
    response.started_at = datetime.now(UTC)
    response.submitted_at = None
    response.quality_flags = None
    response.quality_passed = None
    _log_event(
        db,
        event_type="admin_allow_survey_retake",
        detail=f"授权 {user.nickname}（{user.public_id}）重新作答 BFI-44；原答卷已归档",
        user_id=user.id,
        actor_id=admin.id,
    )
    db.commit()
    return {"ok": True, "retake_count": retake_count + 1}


class SurveyQualityReviewOut(BaseModel):
    user_id: int
    response_id: int
    quality_passed: bool | None
    quality_flags: dict | None
    attention_answers: dict
    diligence_answers: dict
    page_timings_seconds: dict
    blur_count: int
    hard_exclusion: bool
    hard_exclusion_reasons: list[str]
    soft_flags: list[str]
    review_status: str
    review_reason: str | None = None


class SurveyQualityReviewBody(BaseModel):
    status: str = Field(pattern="^(kept|excluded)$")
    reason: str = Field(min_length=2, max_length=500)


def _quality_review_out(response: SurveyResponse, row: SurveyQualityTelemetry | None) -> SurveyQualityReviewOut:
    return SurveyQualityReviewOut(
        user_id=response.user_id,
        response_id=response.id,
        quality_passed=response.quality_passed,
        quality_flags=response.quality_flags,
        attention_answers=dict(row.attention_answers or {}) if row else {},
        diligence_answers=dict(row.diligence_answers or {}) if row else {},
        page_timings_seconds=dict(row.page_timings_seconds or {}) if row else {},
        blur_count=row.blur_count if row else 0,
        hard_exclusion=bool(row and row.hard_exclusion),
        hard_exclusion_reasons=list(row.hard_exclusion_reasons or []) if row else [],
        soft_flags=list(row.soft_flags or []) if row else [],
        review_status=row.admin_review_status if row else "legacy_no_telemetry",
        review_reason=row.admin_review_reason if row else None,
    )


@router.get("/users/{user_id}/survey-quality", response_model=SurveyQualityReviewOut)
def get_survey_quality_review(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = db.get(User, user_id)
    assert_can_manage_participant(db, admin, user)
    response = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.user_id == user_id, SurveyResponse.status == "submitted")
        .order_by(SurveyResponse.id.desc())
        .first()
    )
    if response is None:
        raise HTTPException(status_code=400, detail="该用户尚未正式提交问卷")
    row = db.query(SurveyQualityTelemetry).filter(SurveyQualityTelemetry.response_id == response.id).first()
    return _quality_review_out(response, row)


@router.patch("/users/{user_id}/survey-quality-review", response_model=SurveyQualityReviewOut)
def review_survey_quality(
    user_id: int,
    body: SurveyQualityReviewBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = db.get(User, user_id)
    assert_can_manage_participant(db, admin, user)
    response = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.user_id == user_id, SurveyResponse.status == "submitted")
        .order_by(SurveyResponse.id.desc())
        .first()
    )
    if response is None:
        raise HTTPException(status_code=400, detail="该用户尚未正式提交问卷")
    row = db.query(SurveyQualityTelemetry).filter(SurveyQualityTelemetry.response_id == response.id).first()
    if row is None:
        row = SurveyQualityTelemetry(
            response_id=response.id,
            user_id=user_id,
            attention_answers={},
            diligence_answers={},
            page_timings_seconds={},
            soft_flags=[],
            hard_exclusion_reasons=[],
        )
        db.add(row)
    row.admin_review_status = body.status
    row.admin_review_reason = body.reason.strip()
    row.reviewed_by_user_id = admin.id
    row.reviewed_at = datetime.now(UTC)
    response.quality_passed = body.status == "kept"
    _log_event(
        db,
        event_type="admin_survey_quality_review",
        detail=f"将 {user.nickname}（{user.public_id}）问卷复核为{body.status}：{body.reason.strip()}",
        user_id=user.id,
        actor_id=admin.id,
    )
    db.commit()
    db.refresh(row)
    return _quality_review_out(response, row)


@router.get("/users/{user_id}/personality", response_model=AdminPersonalityOut)
def user_personality(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = db.get(User, user_id)
    assert_can_manage_participant(db, admin, user)
    personality = latest_personality(db, user_id)
    if personality is None:
        raise HTTPException(status_code=400, detail="该用户尚未完成问卷，暂时没有人格画像")
    scores = {
        "E": personality.e,
        "A": personality.a,
        "C": personality.c,
        "N": personality.n,
        "O": personality.o,
    }
    dimensions = [
        DimensionDetail(
            code=code,
            name=PERSONALITY_META[code]["name"],
            english=PERSONALITY_META[code]["english"],
            score=scores[code],
            general=PERSONALITY_META[code]["general"],
            band_text=personality_band(code, scores[code]),
        )
        for code in ("E", "A", "C", "N", "O")
    ]
    return AdminPersonalityOut(
        user_id=user.id,
        nickname=user.nickname,
        public_id=user.public_id,
        summary_label=personality.summary_label,
        scores=scores,
        dimensions=dimensions,
        quality_passed=survey_quality_passed_for_user(db, user_id),
    )


# ---------- 实验管理 ----------


class SceneAdminOut(BaseModel):
    id: int
    scene_key: str
    no: str
    title: str
    short_desc: str
    option_a: str
    option_b: str
    option_a_text: str
    option_b_text: str
    required: bool
    enabled: bool
    sort_order: int


class ExperimentAdminOut(BaseModel):
    id: int
    code: str
    title: str
    status: str
    sort_order: int
    rounds_per_scene: int
    scenes: list[SceneAdminOut]


class ExperimentPatch(BaseModel):
    title: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|active|archived)$")
    rounds_per_scene: int | None = Field(default=None, ge=1, le=50)


class ScenePatch(BaseModel):
    enabled: bool | None = None
    required: bool | None = None
    title: str | None = None
    short_desc: str | None = None
    option_a: str | None = None
    option_b: str | None = None
    option_a_text: str | None = None
    option_b_text: str | None = None


@router.get("/experiments", response_model=list[ExperimentAdminOut])
def list_experiments(db: Session = Depends(get_db), _: User = Depends(get_current_super_admin)):
    rows = (
        db.query(Experiment)
        .options(joinedload(Experiment.scenes))
        .order_by(Experiment.sort_order, Experiment.id)
        .all()
    )
    return [
        ExperimentAdminOut(
            id=e.id,
            code=e.code,
            title=e.title,
            status=e.status,
            sort_order=e.sort_order,
            rounds_per_scene=e.rounds_per_scene,
            scenes=[_scene_out(s) for s in sorted(e.scenes, key=lambda x: x.sort_order)],
        )
        for e in rows
    ]


@router.patch("/experiments/{experiment_id}", response_model=ExperimentAdminOut)
def patch_experiment(
    experiment_id: int,
    body: ExperimentPatch,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    exp = (
        db.query(Experiment)
        .options(joinedload(Experiment.scenes))
        .filter(Experiment.id == experiment_id)
        .first()
    )
    if exp is None:
        raise HTTPException(status_code=404, detail="实验不存在")
    if body.title is not None:
        exp.title = body.title.strip() or exp.title
    if body.status is not None:
        exp.status = body.status
    if body.rounds_per_scene is not None:
        exp.rounds_per_scene = body.rounds_per_scene
    db.commit()
    return _experiment_out(db, exp.id)


def _scene_out(s: ExperimentScene) -> SceneAdminOut:
    return SceneAdminOut(
        id=s.id,
        scene_key=s.scene_key,
        no=s.no,
        title=s.title,
        short_desc=s.short_desc,
        option_a=s.option_a,
        option_b=s.option_b,
        option_a_text=s.option_a_text,
        option_b_text=s.option_b_text,
        required=s.required,
        enabled=s.enabled,
        sort_order=s.sort_order,
    )


def _experiment_out(db: Session, experiment_id: int) -> ExperimentAdminOut:
    exp = (
        db.query(Experiment)
        .options(joinedload(Experiment.scenes))
        .filter(Experiment.id == experiment_id)
        .one()
    )
    return ExperimentAdminOut(
        id=exp.id,
        code=exp.code,
        title=exp.title,
        status=exp.status,
        sort_order=exp.sort_order,
        rounds_per_scene=exp.rounds_per_scene,
        scenes=[_scene_out(s) for s in sorted(exp.scenes, key=lambda x: x.sort_order)],
    )


@router.post("/experiments/{experiment_id}/move")
def move_experiment(
    experiment_id: int,
    direction: int = Query(..., description="1 下移，-1 上移"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    rows = db.query(Experiment).order_by(Experiment.sort_order, Experiment.id).all()
    idx = next((i for i, e in enumerate(rows) if e.id == experiment_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="实验不存在")
    j = idx + direction
    if j < 0 or j >= len(rows):
        return {"ok": True}
    rows[idx].sort_order, rows[j].sort_order = rows[j].sort_order, rows[idx].sort_order
    # normalize
    for i, e in enumerate(sorted(rows, key=lambda x: (x.sort_order, x.id))):
        e.sort_order = i + 1
    db.commit()
    return {"ok": True}


@router.patch("/scenes/{scene_id}", response_model=SceneAdminOut)
def patch_scene(
    scene_id: int,
    body: ScenePatch,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    scene = db.get(ExperimentScene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="场景不存在")
    if body.enabled is not None:
        scene.enabled = body.enabled
    if body.required is not None:
        scene.required = body.required
    if body.title is not None:
        scene.title = body.title.strip() or scene.title
    if body.short_desc is not None:
        scene.short_desc = body.short_desc
    if body.option_a is not None:
        scene.option_a = body.option_a.strip() or scene.option_a
    if body.option_b is not None:
        scene.option_b = body.option_b.strip() or scene.option_b
    if body.option_a_text is not None:
        scene.option_a_text = body.option_a_text
    if body.option_b_text is not None:
        scene.option_b_text = body.option_b_text
    db.commit()
    db.refresh(scene)
    return _scene_out(scene)


# ---------- 页面 / 内容管理（CMS） ----------


class PageAdminOut(BaseModel):
    id: int
    page_key: str
    title: str
    subtitle: str
    status: str
    audience: str
    sort_order: int
    updated_at: datetime | None = None


class PagePatch(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    status: str | None = Field(default=None, pattern="^(published|draft|hidden)$")
    sort_order: int | None = None


class ContentAdminOut(BaseModel):
    id: int
    block_key: str
    title: str
    body: str
    locale: str
    version: int
    updated_at: datetime | None = None


class ContentPatch(BaseModel):
    title: str | None = None
    body: str | None = None


@router.get("/pages", response_model=list[PageAdminOut])
def admin_list_pages(db: Session = Depends(get_db), _: User = Depends(get_current_super_admin)):
    rows = db.query(PageConfig).order_by(PageConfig.sort_order, PageConfig.id).all()
    return [
        PageAdminOut(
            id=r.id,
            page_key=r.page_key,
            title=r.title,
            subtitle=r.subtitle,
            status=r.status,
            audience=r.audience,
            sort_order=r.sort_order,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.patch("/pages/{page_id}", response_model=PageAdminOut)
def admin_patch_page(
    page_id: int,
    body: PagePatch,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    row = db.get(PageConfig, page_id)
    if row is None:
        raise HTTPException(status_code=404, detail="页面不存在")
    if body.title is not None:
        row.title = body.title.strip() or row.title
    if body.subtitle is not None:
        row.subtitle = body.subtitle
    if body.status is not None:
        row.status = body.status
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    db.commit()
    db.refresh(row)
    return PageAdminOut(
        id=row.id,
        page_key=row.page_key,
        title=row.title,
        subtitle=row.subtitle,
        status=row.status,
        audience=row.audience,
        sort_order=row.sort_order,
        updated_at=row.updated_at,
    )


@router.get("/content-blocks", response_model=list[ContentAdminOut])
def admin_list_content(db: Session = Depends(get_db), _: User = Depends(get_current_super_admin)):
    rows = db.query(ContentBlock).order_by(ContentBlock.block_key).all()
    return [
        ContentAdminOut(
            id=r.id,
            block_key=r.block_key,
            title=r.title,
            body=r.body,
            locale=r.locale,
            version=r.version,
            updated_at=r.updated_at,
        )
        for r in rows
        if r.block_key != APP_VERSION_BLOCK_KEY
    ]


class AppVersionOut(BaseModel):
    version: str


class AppVersionPatch(BaseModel):
    version: str = Field(min_length=1, max_length=32)


@router.get("/app-version", response_model=AppVersionOut)
def admin_get_app_version(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    return AppVersionOut(version=get_app_display_version(db))


@router.patch("/app-version", response_model=AppVersionOut)
def admin_patch_app_version(
    body: AppVersionPatch,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_super_admin),
):
    version = set_app_display_version(db, body.version)
    _log_event(
        db,
        event_type="admin_update_app_version",
        detail=f"将平台显示版本号更新为 {version}",
        actor_id=admin.id,
    )
    db.commit()
    return AppVersionOut(version=version)


@router.patch("/content-blocks/{block_id}", response_model=ContentAdminOut)
def admin_patch_content(
    block_id: int,
    body: ContentPatch,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    row = db.get(ContentBlock, block_id)
    if row is None:
        raise HTTPException(status_code=404, detail="内容块不存在")
    if body.title is not None:
        row.title = body.title
    if body.body is not None:
        row.body = body.body
    row.version = (row.version or 1) + 1
    db.commit()
    db.refresh(row)
    return ContentAdminOut(
        id=row.id,
        block_key=row.block_key,
        title=row.title,
        body=row.body,
        locale=row.locale,
        version=row.version,
        updated_at=row.updated_at,
    )


# ---------- 公告栏（测试通告 / 更新日志） ----------


class AnnouncementAdminOut(BaseModel):
    id: int
    kind: str
    title: str
    body: str
    status: str
    pinned: bool
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AnnouncementCreate(BaseModel):
    kind: str = Field(default="notice", description="notice | changelog")
    title: str = Field(min_length=1, max_length=200)
    body: str = ""
    status: str = Field(default="draft", description="published | draft")
    pinned: bool = False


class AnnouncementPatch(BaseModel):
    kind: str | None = None
    title: str | None = None
    body: str | None = None
    status: str | None = None
    pinned: bool | None = None


def _announcement_out(row: Announcement) -> AnnouncementAdminOut:
    return AnnouncementAdminOut(
        id=row.id,
        kind=row.kind,
        title=row.title,
        body=row.body,
        status=row.status,
        pinned=row.pinned,
        published_at=row.published_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _normalize_announcement_kind(kind: str) -> str:
    k = (kind or "").strip().lower()
    if k not in ("notice", "changelog"):
        raise HTTPException(status_code=400, detail="类型须为 notice 或 changelog")
    return k


def _normalize_announcement_status(status: str) -> str:
    s = (status or "").strip().lower()
    if s not in ("published", "draft"):
        raise HTTPException(status_code=400, detail="状态须为 published 或 draft")
    return s


@router.get("/announcements", response_model=list[AnnouncementAdminOut])
def admin_list_announcements(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    rows = db.query(Announcement).order_by(
        Announcement.pinned.desc(),
        Announcement.published_at.desc().nullslast(),
        Announcement.id.desc(),
    ).all()
    return [_announcement_out(r) for r in rows]


@router.post("/announcements", response_model=AnnouncementAdminOut)
def admin_create_announcement(
    body: AnnouncementCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    kind = _normalize_announcement_kind(body.kind)
    status = _normalize_announcement_status(body.status)
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    row = Announcement(
        kind=kind,
        title=title,
        body=(body.body or "").strip(),
        status=status,
        pinned=bool(body.pinned),
        published_at=datetime.now(UTC) if status == "published" else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _announcement_out(row)


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementAdminOut)
def admin_patch_announcement(
    announcement_id: int,
    body: AnnouncementPatch,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    row = db.get(Announcement, announcement_id)
    if row is None:
        raise HTTPException(status_code=404, detail="公告不存在")
    if body.kind is not None:
        row.kind = _normalize_announcement_kind(body.kind)
    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="标题不能为空")
        row.title = title
    if body.body is not None:
        row.body = body.body.strip()
    if body.pinned is not None:
        row.pinned = bool(body.pinned)
    if body.status is not None:
        status = _normalize_announcement_status(body.status)
        was_published = row.status == "published"
        row.status = status
        if status == "published" and (not was_published or row.published_at is None):
            row.published_at = datetime.now(UTC)
        if status == "draft":
            # 下架时保留 published_at，便于重新发布时仍显示原发布时间；也可清空
            pass
    db.commit()
    db.refresh(row)
    return _announcement_out(row)


@router.delete("/announcements/{announcement_id}")
def admin_delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    row = db.get(Announcement, announcement_id)
    if row is None:
        raise HTTPException(status_code=404, detail="公告不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ---------- 邀请码 / 账号事件 ----------


class InviteOut(BaseModel):
    id: int
    code: str
    kind: str
    max_uses: int
    used_count: int
    enabled: bool
    note: str
    owner_id: int | None = None
    owner_nickname: str | None = None
    is_debug: bool = False
    created_at: datetime | None = None


class InviteCreate(BaseModel):
    code: str = Field(min_length=4, max_length=64)
    kind: str = Field(default=INVITE_KIND_PARTICIPANT)
    max_uses: int = Field(default=0, ge=0)
    note: str = ""
    owner_id: int | None = None


class InviteAssignBody(BaseModel):
    owner_id: int | None = None


class SubAdminOut(BaseModel):
    id: int
    nickname: str
    email: str
    public_id: str
    status: str
    invite_code: str | None = None
    invite_code_id: int | None = None
    owned_invite_count: int = 0
    is_debug: bool = False
    created_at: datetime | None = None


def _sub_admin_out(db: Session, user: User) -> SubAdminOut:
    invite_code = None
    invite_code_id = user.invited_by_code_id
    if invite_code_id:
        inv = db.get(InviteCode, invite_code_id)
        invite_code = inv.code if inv else None
    owned_invite_count = (
        db.query(InviteCode)
        .filter(InviteCode.owner_id == user.id, InviteCode.kind == INVITE_KIND_PARTICIPANT)
        .count()
    )
    return SubAdminOut(
        id=user.id,
        nickname=user.nickname,
        email=user.email,
        public_id=user.public_id,
        status=user.status,
        invite_code=invite_code,
        invite_code_id=invite_code_id,
        owned_invite_count=owned_invite_count,
        is_debug=bool(getattr(user, "is_debug", False)),
        created_at=user.created_at,
    )


@router.get("/sub-admins", response_model=list[SubAdminOut])
def get_sub_admins(db: Session = Depends(get_db), admin: User = Depends(get_current_super_admin)):
    return [_sub_admin_out(db, u) for u in list_sub_admins(db, include_debug=is_sudo(admin))]


def _invite_out(db: Session, row: InviteCode) -> InviteOut:
    owner_nickname = None
    if row.owner_id:
        owner = db.get(User, row.owner_id)
        owner_nickname = owner.nickname if owner else None
    return InviteOut(
        id=row.id,
        code=row.code,
        kind=row.kind or INVITE_KIND_PARTICIPANT,
        max_uses=row.max_uses,
        used_count=row.used_count,
        enabled=row.enabled,
        note=row.note,
        owner_id=row.owner_id,
        owner_nickname=owner_nickname,
        is_debug=bool(getattr(row, "is_debug", False)),
        created_at=row.created_at,
    )


@router.get("/invite-codes", response_model=list[InviteOut])
def list_invites(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    q = db.query(InviteCode)
    if not is_super_admin(admin):
        q = q.filter(
            InviteCode.owner_id == admin.id,
            InviteCode.kind == INVITE_KIND_PARTICIPANT,
        )
    elif not is_sudo(admin):
        q = q.filter(InviteCode.is_debug.is_(False))
    rows = q.order_by(InviteCode.id.desc()).all()
    return [_invite_out(db, r) for r in rows]


@router.post("/invite-codes", response_model=InviteOut, status_code=201)
def create_invite(
    body: InviteCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_super_admin),
):
    code = body.code.strip().upper()
    kind = body.kind.strip()
    if kind not in INVITE_KINDS:
        raise HTTPException(status_code=400, detail="邀请码类型无效")
    if db.query(InviteCode).filter(InviteCode.code == code).first():
        raise HTTPException(status_code=400, detail="邀请码已存在")

    owner_id = body.owner_id
    if kind == INVITE_KIND_SUB:
        owner_id = None
    elif owner_id is not None:
        owner = db.get(User, owner_id)
        if owner is None or owner.role != ROLE_SUB:
            raise HTTPException(status_code=400, detail="只能分配给子管理员")

    row = InviteCode(
        code=code,
        kind=kind,
        max_uses=body.max_uses,
        note=body.note.strip(),
        owner_id=owner_id,
        created_by=admin.id,
        enabled=True,
        is_debug=is_sudo(admin),
    )
    db.add(row)
    kind_label = "子管邀请码" if kind == INVITE_KIND_SUB else "员工邀请码"
    if is_sudo(admin):
        kind_label = f"调试{kind_label}"
    owner_part = ""
    if owner_id is not None:
        owner = db.get(User, owner_id)
        owner_part = f"，已分配给 {owner.nickname}" if owner else f"，已分配给用户#{owner_id}"
    _log_event(
        db,
        event_type="invite_created",
        detail=f"创建{kind_label} {code}{owner_part}"
        + (f"（上限 {body.max_uses} 次）" if body.max_uses > 0 else "（不限次数）"),
        actor_id=admin.id,
    )
    db.commit()
    db.refresh(row)
    return _invite_out(db, row)


@router.patch("/invite-codes/{invite_id}/assign", response_model=InviteOut)
def assign_invite(
    invite_id: int,
    body: InviteAssignBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_super_admin),
):
    row = db.get(InviteCode, invite_id)
    if row is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    if (row.kind or INVITE_KIND_PARTICIPANT) != INVITE_KIND_PARTICIPANT:
        raise HTTPException(status_code=400, detail="只有员工邀请码可以分配给子管理员")

    owner_id = body.owner_id
    if owner_id is not None:
        owner = db.get(User, owner_id)
        if owner is None or owner.role != ROLE_SUB:
            raise HTTPException(status_code=400, detail="只能分配给子管理员")
    row.owner_id = owner_id
    if owner_id is None:
        assign_detail = f"取消了邀请码 {row.code} 的子管归属"
    else:
        owner = db.get(User, owner_id)
        name = owner.nickname if owner else f"用户#{owner_id}"
        assign_detail = f"将员工邀请码 {row.code} 分配给子管 {name}"
    _log_event(
        db,
        event_type="invite_assigned",
        detail=assign_detail,
        actor_id=admin.id,
    )
    db.commit()
    db.refresh(row)
    return _invite_out(db, row)


@router.patch("/invite-codes/{invite_id}")
def toggle_invite(
    invite_id: int,
    enabled: bool = Query(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_super_admin),
):
    row = db.get(InviteCode, invite_id)
    if row is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    row.enabled = enabled
    _log_event(
        db,
        event_type="invite_toggled",
        detail=f"{'启用' if enabled else '停用'}了邀请码 {row.code}",
        actor_id=admin.id,
    )
    db.commit()
    return {"ok": True, "enabled": row.enabled}


class AccountEventOut(BaseModel):
    id: int
    event_type: str
    title: str
    detail: str
    user_id: int | None
    actor_id: int | None
    created_at: datetime | None


_EVENT_TITLES = {
    "register": "用户注册",
    "change_password": "修改密码",
    "admin_status_change": "账号状态变更",
    "admin_reset_password": "重置密码",
    "invite_created": "创建邀请码",
    "invite_assigned": "分配邀请码",
    "invite_toggled": "启停邀请码",
}


def _humanize_event_detail(event_type: str, detail: str) -> str:
    """把历史英文/符号明细尽量转成可读中文；新写入的中文明细原样返回。"""
    text = (detail or "").strip()
    if not text:
        return "无更多说明"

    # 已是中文为主的新格式
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return text

    if event_type == "admin_status_change" and "->" in text:
        left, right = [p.strip() for p in text.split("->", 1)]
        status = "正常启用" if right == "active" else "已禁用" if right == "disabled" else right
        return f"将 {left} 设为{status}"

    if event_type == "admin_reset_password":
        return text.replace("重置", "重置了").replace(" 密码", " 的登录密码")

    if event_type == "invite_created":
        # YM2026 kind=participant owner=3
        parts = text.split()
        code = parts[0] if parts else text
        kind = "员工邀请码"
        owner = ""
        for p in parts[1:]:
            if p.startswith("kind="):
                kind = "子管邀请码" if p.endswith("sub_admin") else "员工邀请码"
            if p.startswith("owner=") and p != "owner=None":
                owner = f"，归属用户#{p.split('=', 1)[1]}"
        return f"创建{kind} {code}{owner}"

    if event_type == "invite_assigned" and "->" in text:
        left, right = [p.strip() for p in text.split("->", 1)]
        code = left.split()[0] if left else left
        if "None" in right or right.endswith("owner=None"):
            return f"取消了邀请码 {code} 的子管归属"
        oid = right.split("=")[-1]
        return f"将邀请码 {code} 分配给用户#{oid}"

    if event_type == "invite_toggled" and "->" in text:
        left, right = [p.strip() for p in text.split("->", 1)]
        code = left.split()[0] if left else left
        on = right.lower() in {"true", "1", "yes"}
        return f"{'启用' if on else '停用'}了邀请码 {code}"

    if event_type == "register":
        return text.replace("注册成功", "完成注册")

    return text


@router.get("/account-events", response_model=list[AccountEventOut])
def list_events(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_super_admin),
):
    rows = db.query(AccountEvent).order_by(AccountEvent.id.desc()).limit(limit).all()
    return [
        AccountEventOut(
            id=r.id,
            event_type=r.event_type,
            title=_EVENT_TITLES.get(r.event_type, r.event_type),
            detail=_humanize_event_detail(r.event_type, r.detail),
            user_id=r.user_id,
            actor_id=r.actor_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ---------- 研究数据导出 ----------


@router.get("/export/{kind}")
def export_research_data(
    kind: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
    filename: str | None = Query(None, max_length=120),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_super_admin),
):
    """导出研究数据。kind: users | survey-answers | survey-quality | runs；format: csv|json。"""
    allowed = {"users", "survey-answers", "survey-quality", "runs"}
    if kind not in allowed:
        raise HTTPException(status_code=404, detail="未知导出类型")
    return export_dataset(
        db,
        admin,
        kind=kind,  # type: ignore[arg-type]
        fmt=format,  # type: ignore[arg-type]
        filename=filename,
    )

