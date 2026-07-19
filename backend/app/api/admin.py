import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_admin, get_current_super_admin
from app.core.database import get_db
from app.core.roles import (
    INVITE_KIND_PARTICIPANT,
    INVITE_KIND_SUB,
    INVITE_KINDS,
    ROLE_SUB,
    is_super_admin,
)
from app.core.security import hash_password
from app.data.personality_meta import PERSONALITY_META, personality_band
from app.models.admin_extra import AccountEvent, InviteCode
from app.models.cms import ContentBlock, PageConfig
from app.models.game import Experiment, ExperimentScene, GameRound, GameSession
from app.models.survey import SurveyAnswer, SurveyResponse
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
    list_sub_admins,
    participant_query_for_staff,
)
from app.services.stats import (
    admin_overview_stats,
    latest_personality,
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
    items = []
    for u in users:
        total, sessions = user_game_stats(db, u.id)
        personality = latest_personality(db, u.id)
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
                survey_status=survey_status_for_user(db, u.id),
                has_personality=personality is not None,
                status=u.status,
            )
        )
    return AdminUsersOut(total=len(items), items=items)


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
    assert_can_manage_participant(db, admin, user)
    user.status = body.status
    _log_event(
        db,
        event_type="admin_status_change",
        detail=f"{user.public_id} -> {body.status}",
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
        detail=f"重置 {user.public_id} 密码",
        user_id=user.id,
        actor_id=admin.id,
    )
    db.commit()
    return {"ok": True}


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
    ]


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
        created_at=row.created_at,
    )


@router.get("/sub-admins", response_model=list[SubAdminOut])
def get_sub_admins(db: Session = Depends(get_db), _: User = Depends(get_current_super_admin)):
    return [
        SubAdminOut(id=u.id, nickname=u.nickname, email=u.email, public_id=u.public_id)
        for u in list_sub_admins(db)
    ]


@router.get("/invite-codes", response_model=list[InviteOut])
def list_invites(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    q = db.query(InviteCode)
    if not is_super_admin(admin):
        q = q.filter(
            InviteCode.owner_id == admin.id,
            InviteCode.kind == INVITE_KIND_PARTICIPANT,
        )
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
    )
    db.add(row)
    _log_event(
        db,
        event_type="invite_created",
        detail=f"{code} kind={kind} owner={owner_id}",
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
    _log_event(
        db,
        event_type="invite_assigned",
        detail=f"{row.code} -> owner={owner_id}",
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
        detail=f"{row.code} -> {enabled}",
        actor_id=admin.id,
    )
    db.commit()
    return {"ok": True, "enabled": row.enabled}


class AccountEventOut(BaseModel):
    id: int
    event_type: str
    detail: str
    user_id: int | None
    actor_id: int | None
    created_at: datetime | None


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
            detail=r.detail,
            user_id=r.user_id,
            actor_id=r.actor_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ---------- CSV 导出 ----------


def _csv_response(filename: str, rows: list[list]) -> StreamingResponse:
    buf = io.StringIO()
    buf.write("\ufeff")  # Excel UTF-8 BOM
    writer = csv.writer(buf)
    writer.writerows(rows)
    data = buf.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/users.csv")
def export_users(db: Session = Depends(get_db), _: User = Depends(get_current_super_admin)):
    header = [
        "id",
        "public_id",
        "nickname",
        "email",
        "status",
        "survey_status",
        "total_score",
        "sessions_count",
        "E",
        "A",
        "C",
        "N",
        "O",
        "summary",
        "created_at",
    ]
    rows: list[list] = [header]
    users = db.query(User).filter(User.role == "participant").order_by(User.id).all()
    for u in users:
        total, sessions = user_game_stats(db, u.id)
        p = latest_personality(db, u.id)
        rows.append(
            [
                u.id,
                u.public_id,
                u.nickname,
                u.email,
                u.status,
                survey_status_for_user(db, u.id),
                total,
                sessions,
                p.e if p else "",
                p.a if p else "",
                p.c if p else "",
                p.n if p else "",
                p.o if p else "",
                p.summary_label if p else "",
                u.created_at.isoformat() if u.created_at else "",
            ]
        )
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return _csv_response(f"yangmind_users_{stamp}.csv", rows)


@router.get("/export/surveys.csv")
def export_surveys(db: Session = Depends(get_db), _: User = Depends(get_current_super_admin)):
    header = ["user_public_id", "nickname", "email", "response_id", "status", "item_no", "value", "submitted_at"]
    rows: list[list] = [header]
    responses = (
        db.query(SurveyResponse)
        .options(joinedload(SurveyResponse.answers))
        .order_by(SurveyResponse.id)
        .all()
    )
    for resp in responses:
        user = db.get(User, resp.user_id)
        if user is None:
            continue
        answers = sorted(resp.answers, key=lambda a: a.item_no)
        if not answers:
            rows.append(
                [
                    user.public_id,
                    user.nickname,
                    user.email,
                    resp.id,
                    resp.status,
                    "",
                    "",
                    resp.submitted_at.isoformat() if resp.submitted_at else "",
                ]
            )
            continue
        for a in answers:
            rows.append(
                [
                    user.public_id,
                    user.nickname,
                    user.email,
                    resp.id,
                    resp.status,
                    a.item_no,
                    a.value,
                    resp.submitted_at.isoformat() if resp.submitted_at else "",
                ]
            )
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return _csv_response(f"yangmind_surveys_{stamp}.csv", rows)


@router.get("/export/rounds.csv")
def export_rounds(db: Session = Depends(get_db), _: User = Depends(get_current_super_admin)):
    header = [
        "user_public_id",
        "nickname",
        "session_id",
        "experiment_id",
        "scene_key",
        "session_status",
        "round_no",
        "my_choice",
        "opponent_choice",
        "my_points",
        "opponent_points",
        "session_my_score",
        "session_opponent_score",
    ]
    rows: list[list] = [header]
    sessions = (
        db.query(GameSession)
        .options(joinedload(GameSession.rounds), joinedload(GameSession.scene))
        .order_by(GameSession.id)
        .all()
    )
    for sess in sessions:
        user = db.get(User, sess.user_id)
        if user is None:
            continue
        scene_key = sess.scene.scene_key if sess.scene else ""
        rounds = sorted(sess.rounds, key=lambda r: r.round_no)
        if not rounds:
            rows.append(
                [
                    user.public_id,
                    user.nickname,
                    sess.id,
                    sess.experiment_id,
                    scene_key,
                    sess.status,
                    "",
                    "",
                    "",
                    "",
                    "",
                    sess.my_score,
                    sess.opponent_score,
                ]
            )
            continue
        for r in rounds:
            rows.append(
                [
                    user.public_id,
                    user.nickname,
                    sess.id,
                    sess.experiment_id,
                    scene_key,
                    sess.status,
                    r.round_no,
                    r.my_choice,
                    r.opponent_choice,
                    r.my_points,
                    r.opponent_points,
                    sess.my_score,
                    sess.opponent_score,
                ]
            )
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return _csv_response(f"yangmind_rounds_{stamp}.csv", rows)
