from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.data.bfi44_seed import INSTRUMENT_CODE
from app.models.survey import (
    PersonalityScore,
    SurveyAnswer,
    SurveyInstrument,
    SurveyItem,
    SurveyResponse,
)
from app.models.user import User
from app.schemas.survey import (
    MyResponseOut,
    PersonalityScoreOut,
    SaveAnswersRequest,
    SubmitSurveyRequest,
    SurveyInstrumentOut,
    SurveyItemOut,
    QualityCheckOut,
)
from app.services.bfi_scoring import (
    ATTENTION_CHECKS,
    build_summary_label,
    check_quality,
    compute_dimension_scores,
)
from app.services.experiment_progress import personality_feedback_unlocked

router = APIRouter(prefix="/api/v1/surveys", tags=["surveys"])


def _elapsed_seconds(started_at: datetime | None) -> float | None:
    if started_at is None:
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    return max((datetime.now(UTC) - started_at).total_seconds(), 0)


def _get_instrument(db: Session) -> SurveyInstrument:
    instrument = (
        db.query(SurveyInstrument)
        .options(joinedload(SurveyInstrument.items))
        .filter(SurveyInstrument.code == INSTRUMENT_CODE)
        .first()
    )
    if instrument is None:
        raise HTTPException(status_code=500, detail="题库未初始化，请重启后端")
    return instrument


def _get_or_create_draft(db: Session, user: User, instrument: SurveyInstrument) -> SurveyResponse:
    submitted = (
        db.query(SurveyResponse)
        .filter(
            SurveyResponse.user_id == user.id,
            SurveyResponse.instrument_id == instrument.id,
            SurveyResponse.status == "submitted",
        )
        .first()
    )
    if submitted:
        raise HTTPException(status_code=400, detail="你已提交过 BFI-44，不能再修改答案")

    drafts = (
        db.query(SurveyResponse)
        .filter(
            SurveyResponse.user_id == user.id,
            SurveyResponse.instrument_id == instrument.id,
            SurveyResponse.status == "in_progress",
        )
        .order_by(SurveyResponse.id.asc())
        .all()
    )
    if drafts:
        keep = drafts[-1]
        for extra in drafts[:-1]:
            db.query(SurveyAnswer).filter(SurveyAnswer.response_id == extra.id).delete()
            db.delete(extra)
        if len(drafts) > 1:
            db.commit()
            db.refresh(keep)
        return keep

    draft = SurveyResponse(
        user_id=user.id,
        instrument_id=instrument.id,
        instrument_version=instrument.version,
        status="in_progress",
    )
    db.add(draft)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(SurveyResponse)
            .filter(
                SurveyResponse.user_id == user.id,
                SurveyResponse.instrument_id == instrument.id,
            )
            .order_by(SurveyResponse.id.desc())
            .first()
        )
        if existing is None:
            raise
        if existing.status == "submitted":
            raise HTTPException(status_code=400, detail="你已提交过 BFI-44，不能再修改答案")
        return existing
    db.refresh(draft)
    return draft


def _answers_map(response: SurveyResponse | None) -> dict[int, int]:
    if response is None:
        return {}
    return {a.item_no: a.value for a in response.answers}


@router.get("/bfi-44", response_model=SurveyInstrumentOut)
def get_bfi44(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """拉取 BFI-44 题目（需登录）。"""
    instrument = _get_instrument(db)
    items = sorted(instrument.items, key=lambda x: x.sort_order)
    return SurveyInstrumentOut(
        code=instrument.code,
        version=instrument.version,
        title=instrument.title,
        item_count=instrument.item_count,
        items=[
            SurveyItemOut(item_no=i.item_no, stem=i.stem, sort_order=i.sort_order) for i in items
        ],
        quality_checks=[
            QualityCheckOut(check_id=check["check_id"], stem=check["stem"])
            for check in ATTENTION_CHECKS
        ],
    )


@router.get("/bfi-44/my-response", response_model=MyResponseOut)
def my_response(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查看我的问卷进度或已提交结果。"""
    instrument = _get_instrument(db)
    # 优先已提交结果，避免并发草稿盖住已提交记录
    response = (
        db.query(SurveyResponse)
        .options(
            joinedload(SurveyResponse.answers),
            joinedload(SurveyResponse.personality_score),
        )
        .filter(
            SurveyResponse.user_id == current_user.id,
            SurveyResponse.instrument_id == instrument.id,
            SurveyResponse.status == "submitted",
        )
        .order_by(SurveyResponse.id.desc())
        .first()
    )
    if response is None:
        response = (
            db.query(SurveyResponse)
            .options(
                joinedload(SurveyResponse.answers),
                joinedload(SurveyResponse.personality_score),
            )
            .filter(
                SurveyResponse.user_id == current_user.id,
                SurveyResponse.instrument_id == instrument.id,
            )
            .order_by(SurveyResponse.id.desc())
            .first()
        )
    if response is None:
        return MyResponseOut(status="none", answered_count=0, unlock_games=False)

    amap = _answers_map(response)
    feedback_unlocked = response.status == "submitted" and personality_feedback_unlocked(
        db, current_user.id
    )
    personality = None
    if feedback_unlocked and response.personality_score is not None:
        personality = PersonalityScoreOut.model_validate(response.personality_score)

    return MyResponseOut(
        status=response.status,
        answered_count=len(amap),
        answers={str(k): v for k, v in amap.items()},
        personality=personality,
        quality_passed=response.quality_passed if feedback_unlocked else None,
        unlock_games=response.status == "submitted",
        feedback_unlocked=feedback_unlocked,
    )


@router.put("/bfi-44/answers", response_model=MyResponseOut)
def save_answers(
    body: SaveAnswersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存/更新部分或全部答案（草稿）。"""
    instrument = _get_instrument(db)
    draft = _get_or_create_draft(db, current_user, instrument)

    existing = {a.item_no: a for a in draft.answers}
    for item in body.answers:
        if item.item_no < 1 or item.item_no > instrument.item_count:
            raise HTTPException(status_code=400, detail=f"题号无效: {item.item_no}")
        if item.item_no in existing:
            existing[item.item_no].value = item.value
            existing[item.item_no].answered_at = datetime.now(UTC)
        else:
            db.add(
                SurveyAnswer(
                    response_id=draft.id,
                    item_no=item.item_no,
                    value=item.value,
                )
            )
    db.commit()

    db.refresh(draft)
    draft = (
        db.query(SurveyResponse)
        .options(joinedload(SurveyResponse.answers))
        .filter(SurveyResponse.id == draft.id)
        .one()
    )
    amap = _answers_map(draft)
    return MyResponseOut(
        status=draft.status,
        answered_count=len(amap),
        answers={str(k): v for k, v in amap.items()},
        unlock_games=False,
    )


@router.post("/bfi-44/submit", response_model=MyResponseOut)
def submit(
    body: SubmitSurveyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """正式提交：必须 44 题齐全 → 质量检查 → 计分 → 解锁博弈。"""
    instrument = _get_instrument(db)

    already = (
        db.query(SurveyResponse)
        .filter(
            SurveyResponse.user_id == current_user.id,
            SurveyResponse.instrument_id == instrument.id,
            SurveyResponse.status == "submitted",
        )
        .first()
    )
    if already:
        raise HTTPException(status_code=400, detail="你已提交过 BFI-44")

    draft = (
        db.query(SurveyResponse)
        .options(joinedload(SurveyResponse.answers))
        .filter(
            SurveyResponse.user_id == current_user.id,
            SurveyResponse.instrument_id == instrument.id,
            SurveyResponse.status == "in_progress",
        )
        .first()
    )
    if draft is None:
        raise HTTPException(status_code=400, detail="还没有作答记录，请先答题")

    amap = _answers_map(draft)
    missing = [i for i in range(1, instrument.item_count + 1) if i not in amap]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"还有 {len(missing)} 题未完成，请检查后提交",
        )

    items_meta = (
        db.query(SurveyItem)
        .filter(SurveyItem.instrument_id == instrument.id)
        .order_by(SurveyItem.item_no)
        .all()
    )
    meta = [(i.item_no, i.dimension, i.reverse_scored) for i in items_meta]
    scores = compute_dimension_scores(amap, meta)
    allowed_check_ids = {check["check_id"] for check in ATTENTION_CHECKS}
    attention_answers = {item.check_id: item.value for item in body.attention_answers}
    if set(attention_answers) != allowed_check_ids:
        raise HTTPException(status_code=400, detail="请完成全部作答确认题")
    passed, flags = check_quality(
        amap,
        duration_seconds=_elapsed_seconds(draft.started_at),
        attention_answers=attention_answers,
    )

    draft.status = "submitted"
    draft.submitted_at = datetime.now(UTC)
    draft.quality_flags = flags
    draft.quality_passed = passed

    personality = PersonalityScore(
        user_id=current_user.id,
        response_id=draft.id,
        e=scores["E"],
        a=scores["A"],
        c=scores["C"],
        n=scores["N"],
        o=scores["O"],
        summary_label=build_summary_label(scores),
    )
    db.add(personality)
    db.commit()

    db.refresh(draft)
    draft = (
        db.query(SurveyResponse)
        .options(
            joinedload(SurveyResponse.answers),
            joinedload(SurveyResponse.personality_score),
        )
        .filter(SurveyResponse.id == draft.id)
        .one()
    )

    return MyResponseOut(
        status=draft.status,
        answered_count=44,
        answers={str(k): v for k, v in amap.items()},
        personality=None,
        quality_passed=None,
        unlock_games=True,
        feedback_unlocked=False,
    )


@router.post("/bfi-44/retake", response_model=MyResponseOut)
def retake(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """正式答卷必须保留，避免获知质量结果后反复作答造成选择偏差。"""
    instrument = _get_instrument(db)
    response = (
        db.query(SurveyResponse)
        .options(
            joinedload(SurveyResponse.answers),
            joinedload(SurveyResponse.personality_score),
        )
        .filter(
            SurveyResponse.user_id == current_user.id,
            SurveyResponse.instrument_id == instrument.id,
        )
        .order_by(SurveyResponse.id.desc())
        .first()
    )
    if response is None:
        raise HTTPException(status_code=400, detail="还没有问卷记录")
    raise HTTPException(status_code=400, detail="正式问卷已提交，不能重新作答")
