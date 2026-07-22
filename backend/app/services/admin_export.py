"""管理端研究数据导出：用户层 / 问卷答卷 / 问卷质量 / 博弈轮次。"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi.responses import Response, StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.roles import is_sudo
from app.models.game import GameComprehension, GameSession
from app.models.match import PvpDecisionTelemetry, PvpMatch
from app.models.survey import SurveyQualityTelemetry, SurveyResponse, SurveyRetakeArchive
from app.models.user import User
from app.services.stats import (
    latest_personality,
    survey_quality_passed_for_user,
    survey_status_for_user,
    user_game_stats,
)

ExportKind = Literal["users", "survey-answers", "survey-quality", "runs"]
ExportFormat = Literal["csv", "json"]

_CATEGORY_ZH = {
    "response_behavior": "作答行为异常",
    "very_fast": "作答过快",
    "attention_check": "注意力检测未通过",
}
_SOFT_ZH = {
    "response_behavior": "作答行为异常",
    "very_fast": "作答过快",
    "attention_check": "注意力检测未通过",
    "self_report_low_diligence": "自报不够认真",
    "self_report_technical_issue": "自报技术故障",
    "frequent_focus_loss": "频繁失焦",
    "duplicate_device_review": "疑似重复设备",
}
_HARD_ZH = {
    "all_attention_checks_failed": "两道注意力题均未通过",
}
_BEHAVIOR_ZH = {
    "longstring": "连续同答过长",
    "dominant_option": "单一选项占比过高",
    "low_variability": "作答变异过低",
    "inconsistent_pairs": "正反题不一致",
}
_STATUS_ZH = {
    "active": "正常",
    "disabled": "已禁用",
    "submitted": "已提交",
    "in_progress": "作答中",
    "pending": "待复核",
    "kept": "已保留",
    "excluded": "已排除",
    "not_needed": "无需复核",
}


def _bool_zh(value: Any) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return ""


def _quality_status_zh(passed: bool | None, survey_status: str) -> str:
    if survey_status in ("未完成", "作答中"):
        return "尚未提交"
    if passed is True:
        return "通过"
    if passed is False:
        return "未通过"
    return "未知"


def _join_zh(items: list[str] | None, mapping: dict[str, str] | None = None) -> str:
    if not items:
        return ""
    if mapping:
        return "；".join(mapping.get(str(x), str(x)) for x in items)
    return "；".join(str(x) for x in items)


def _kv_zh(data: dict | None) -> str:
    if not data:
        return ""
    return "；".join(f"{k}={v}" for k, v in data.items())


def _safe_filename(name: str, fmt: ExportFormat) -> str:
    base = (name or "").strip()
    base = re.sub(r"[\\/:*?\"<>|]+", "_", base)
    base = base.strip(". ") or "export"
    if base.lower().endswith((".csv", ".json")):
        base = base.rsplit(".", 1)[0]
    return f"{base}.{fmt}"


def _default_basename(kind: ExportKind, include_debug: bool) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    prefix = {
        "users": "users",
        "survey-answers": "survey_answers",
        "survey-quality": "survey_quality",
        "runs": "runs",
    }[kind]
    debug = "debug_" if include_debug else ""
    return f"{prefix}_{debug}{stamp}"


def file_response(
    *,
    kind: ExportKind,
    fmt: ExportFormat,
    rows_or_records: list[list] | list[dict],
    filename: str | None,
    include_debug: bool,
) -> Response:
    name = _safe_filename(filename or _default_basename(kind, include_debug), fmt)
    if fmt == "json":
        payload = json.dumps(rows_or_records, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=payload,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerows(rows_or_records)  # type: ignore[arg-type]
    data = buf.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def build_users_export(db: Session, *, include_debug: bool, fmt: ExportFormat):
    q = db.query(User).filter(User.role == "participant")
    if not include_debug:
        q = q.filter(User.is_debug.is_(False))
    users = q.order_by(User.id).all()

    if fmt == "json":
        records = []
        for u in users:
            total, sessions = user_game_stats(db, u.id)
            p = latest_personality(db, u.id)
            status = survey_status_for_user(db, u.id)
            quality = survey_quality_passed_for_user(db, u.id)
            records.append(
                {
                    "id": u.id,
                    "public_id": u.public_id,
                    "nickname": u.nickname,
                    "email": u.email,
                    "status": u.status,
                    "is_debug": bool(getattr(u, "is_debug", False)),
                    "survey_status": status,
                    "survey_quality_passed": quality,
                    "personality": {
                        "e": p.e if p else None,
                        "a": p.a if p else None,
                        "c": p.c if p else None,
                        "n": p.n if p else None,
                        "o": p.o if p else None,
                        "summary_label": p.summary_label if p else None,
                    },
                    "sessions_count": sessions,
                    "total_score": total,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
            )
        return records

    header = [
        "内部ID",
        "公开ID",
        "昵称",
        "邮箱",
        "账号状态",
        "调试账号",
        "问卷完成状态",
        "问卷质量状态",
        "外向性E",
        "宜人性A",
        "尽责性C",
        "情绪敏感N",
        "开放性O",
        "人格摘要",
        "完成博弈场次",
        "博弈总得分",
        "注册时间",
    ]
    rows: list[list] = [header]
    for u in users:
        total, sessions = user_game_stats(db, u.id)
        p = latest_personality(db, u.id)
        status = survey_status_for_user(db, u.id)
        quality = survey_quality_passed_for_user(db, u.id)
        rows.append(
            [
                u.id,
                u.public_id,
                u.nickname,
                u.email,
                _STATUS_ZH.get(u.status, u.status),
                _bool_zh(getattr(u, "is_debug", False)),
                status,
                _quality_status_zh(quality, status),
                p.e if p else "",
                p.a if p else "",
                p.c if p else "",
                p.n if p else "",
                p.o if p else "",
                p.summary_label if p else "",
                sessions,
                total,
                u.created_at.isoformat() if u.created_at else "",
            ]
        )
    return rows


def _answer_map(answers) -> dict[int, Any]:
    out: dict[int, Any] = {}
    for a in answers:
        if isinstance(a, dict):
            item_no = a.get("item_no")
            value = a.get("value")
        else:
            item_no = a.item_no
            value = a.value
        if item_no is not None:
            out[int(item_no)] = value
    return out


def build_survey_answers_export(db: Session, *, include_debug: bool, fmt: ExportFormat):
    item_cols = [f"题{i}" for i in range(1, 45)]
    if fmt == "csv":
        header = [
            "记录来源",
            "重做序号",
            "授权管理员公开ID",
            "归档时间",
            "公开ID",
            "昵称",
            "邮箱",
            "调试账号",
            "答卷ID",
            "答卷状态",
            "问卷是否通过质量",
            *item_cols,
            "提交时间",
        ]
        rows: list[list] = [header]
    else:
        rows = []  # type: ignore[assignment]
        records: list[dict] = []

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
        if not include_debug and getattr(user, "is_debug", False):
            continue
        amap = _answer_map(resp.answers)
        item_values = [amap.get(i, "") for i in range(1, 45)]
        submitted = resp.submitted_at.isoformat() if resp.submitted_at else ""
        if fmt == "json":
            records.append(
                {
                    "record_source": "current",
                    "retake_no": None,
                    "authorized_by_public_id": None,
                    "archived_at": None,
                    "user_public_id": user.public_id,
                    "nickname": user.nickname,
                    "email": user.email,
                    "is_debug": bool(getattr(user, "is_debug", False)),
                    "response_id": resp.id,
                    "status": resp.status,
                    "quality_passed": resp.quality_passed,
                    "answers": {str(i): amap.get(i) for i in range(1, 45)},
                    "submitted_at": submitted or None,
                }
            )
        else:
            rows.append(
                [
                    "当前正式答卷",
                    "",
                    "",
                    "",
                    user.public_id,
                    user.nickname,
                    user.email,
                    _bool_zh(getattr(user, "is_debug", False)),
                    resp.id,
                    _STATUS_ZH.get(resp.status, resp.status),
                    _bool_zh(resp.quality_passed),
                    *item_values,
                    submitted,
                ]
            )

    archives = db.query(SurveyRetakeArchive).order_by(SurveyRetakeArchive.id).all()
    for archive in archives:
        user = db.get(User, archive.user_id)
        actor = db.get(User, archive.authorized_by_user_id)
        if user is None:
            continue
        if not include_debug and getattr(user, "is_debug", False):
            continue
        snapshot = archive.response_snapshot or {}
        response_data = snapshot.get("response") or {}
        answers = snapshot.get("answers") or []
        amap = _answer_map(answers)
        item_values = [amap.get(i, "") for i in range(1, 45)]
        submitted = response_data.get("submitted_at") or ""
        if fmt == "json":
            records.append(
                {
                    "record_source": "archived_before_retake",
                    "retake_no": archive.retake_no,
                    "authorized_by_public_id": actor.public_id if actor else None,
                    "archived_at": archive.archived_at.isoformat() if archive.archived_at else None,
                    "user_public_id": user.public_id,
                    "nickname": user.nickname,
                    "email": user.email,
                    "is_debug": bool(getattr(user, "is_debug", False)),
                    "response_id": archive.original_response_id,
                    "status": "submitted",
                    "quality_passed": response_data.get("quality_passed"),
                    "answers": {str(i): amap.get(i) for i in range(1, 45)},
                    "submitted_at": submitted or None,
                }
            )
        else:
            rows.append(
                [
                    "重做前归档",
                    archive.retake_no,
                    actor.public_id if actor else "",
                    archive.archived_at.isoformat() if archive.archived_at else "",
                    user.public_id,
                    user.nickname,
                    user.email,
                    _bool_zh(getattr(user, "is_debug", False)),
                    archive.original_response_id,
                    "已提交",
                    _bool_zh(response_data.get("quality_passed")),
                    *item_values,
                    submitted,
                ]
            )

    return records if fmt == "json" else rows


def _quality_row_common(
    *,
    record_source: str,
    retake_no: Any,
    actor_public_id: str,
    archived_at: str,
    user: User,
    response_id: Any,
    status: str,
    quality_passed: Any,
    quality_flags: dict | None,
    telemetry: SurveyQualityTelemetry | dict | None,
) -> tuple[list, dict]:
    if isinstance(telemetry, SurveyQualityTelemetry):
        attention = telemetry.attention_answers or {}
        diligence = telemetry.diligence_answers or {}
        timings = telemetry.page_timings_seconds or {}
        blur = telemetry.blur_count
        hard = telemetry.hard_exclusion
        hard_reasons = telemetry.hard_exclusion_reasons or []
        soft = telemetry.soft_flags or []
        review_status = telemetry.admin_review_status or ""
        review_reason = telemetry.admin_review_reason or ""
    elif isinstance(telemetry, dict):
        attention = telemetry.get("attention_answers") or {}
        diligence = telemetry.get("diligence_answers") or {}
        timings = telemetry.get("page_timings_seconds") or {}
        blur = telemetry.get("blur_count", "")
        hard = telemetry.get("hard_exclusion", "")
        hard_reasons = telemetry.get("hard_exclusion_reasons") or []
        soft = telemetry.get("soft_flags") or []
        review_status = telemetry.get("admin_review_status", "")
        review_reason = telemetry.get("admin_review_reason", "")
    else:
        attention, diligence, timings = {}, {}, {}
        blur, hard, hard_reasons, soft = "", "", [], []
        review_status, review_reason = "", ""

    flags = quality_flags or {}
    csv_row = [
        record_source,
        retake_no,
        actor_public_id,
        archived_at,
        user.public_id,
        user.nickname,
        user.email,
        _bool_zh(getattr(user, "is_debug", False)),
        response_id,
        _STATUS_ZH.get(status, status) if isinstance(status, str) else status,
        _bool_zh(quality_passed),
        flags.get("rule_version", ""),
        flags.get("max_same_streak", ""),
        flags.get("unique_response_count", ""),
        flags.get("response_sd", ""),
        flags.get("dominant_option_share", ""),
        flags.get("mean_consistency_pair_gap", ""),
        flags.get("large_consistency_pair_gaps", ""),
        flags.get("duration_seconds", ""),
        _join_zh(flags.get("attention_failed") or []),
        _join_zh(flags.get("response_behavior_reasons") or [], _BEHAVIOR_ZH),
        _join_zh(flags.get("triggered_categories") or [], _CATEGORY_ZH),
        _bool_zh(flags.get("review_recommended")),
        _kv_zh(attention if isinstance(attention, dict) else {}),
        diligence.get("diligence_read", "") if isinstance(diligence, dict) else "",
        diligence.get("diligence_authentic", "") if isinstance(diligence, dict) else "",
        diligence.get("diligence_technical", "") if isinstance(diligence, dict) else "",
        _kv_zh(timings if isinstance(timings, dict) else {}),
        blur,
        _bool_zh(hard) if hard != "" else "",
        _join_zh(list(hard_reasons), _HARD_ZH),
        _join_zh(list(soft), _SOFT_ZH),
        _STATUS_ZH.get(str(review_status), review_status),
        review_reason,
    ]
    json_record = {
        "record_source": "current" if record_source == "当前正式答卷" else "archived_before_retake",
        "retake_no": retake_no if retake_no != "" else None,
        "authorized_by_public_id": actor_public_id or None,
        "archived_at": archived_at or None,
        "user_public_id": user.public_id,
        "nickname": user.nickname,
        "email": user.email,
        "is_debug": bool(getattr(user, "is_debug", False)),
        "response_id": response_id,
        "status": status,
        "quality_passed": quality_passed,
        "quality_flags": flags,
        "attention_answers": attention,
        "diligence_answers": diligence,
        "page_timings_seconds": timings,
        "blur_count": blur,
        "hard_exclusion": hard,
        "hard_exclusion_reasons": hard_reasons,
        "soft_flags": soft,
        "admin_review_status": review_status,
        "admin_review_reason": review_reason,
    }
    return csv_row, json_record


def build_survey_quality_export(db: Session, *, include_debug: bool, fmt: ExportFormat):
    header = [
        "记录来源",
        "重做序号",
        "授权管理员公开ID",
        "归档时间",
        "公开ID",
        "昵称",
        "邮箱",
        "调试账号",
        "答卷ID",
        "答卷状态",
        "是否通过质量",
        "规则版本",
        "最长连续同答",
        "不同选项个数",
        "作答标准差",
        "主导选项占比",
        "正反题平均差距",
        "大差距题对数",
        "作答总秒数",
        "注意力未通过题",
        "作答行为原因",
        "触发类别",
        "建议人工复核",
        "注意力题作答",
        "自报认真阅读",
        "自报真实作答",
        "自报技术问题",
        "各组作答秒数",
        "失焦次数",
        "硬性排除",
        "硬性排除原因",
        "软标记",
        "管理员复核状态",
        "管理员复核理由",
    ]
    rows: list[list] = [header]
    records: list[dict] = []

    responses = db.query(SurveyResponse).order_by(SurveyResponse.id).all()
    for resp in responses:
        user = db.get(User, resp.user_id)
        if user is None:
            continue
        if not include_debug and getattr(user, "is_debug", False):
            continue
        telemetry = (
            db.query(SurveyQualityTelemetry)
            .filter(SurveyQualityTelemetry.response_id == resp.id)
            .first()
        )
        csv_row, json_record = _quality_row_common(
            record_source="当前正式答卷",
            retake_no="",
            actor_public_id="",
            archived_at="",
            user=user,
            response_id=resp.id,
            status=resp.status,
            quality_passed=resp.quality_passed,
            quality_flags=resp.quality_flags if isinstance(resp.quality_flags, dict) else {},
            telemetry=telemetry,
        )
        if fmt == "json":
            records.append(json_record)
        else:
            rows.append(csv_row)

    archives = db.query(SurveyRetakeArchive).order_by(SurveyRetakeArchive.id).all()
    for archive in archives:
        user = db.get(User, archive.user_id)
        actor = db.get(User, archive.authorized_by_user_id)
        if user is None:
            continue
        if not include_debug and getattr(user, "is_debug", False):
            continue
        snapshot = archive.response_snapshot or {}
        response_data = snapshot.get("response") or {}
        telemetry_data = snapshot.get("quality_telemetry") or {}
        csv_row, json_record = _quality_row_common(
            record_source="重做前归档",
            retake_no=archive.retake_no,
            actor_public_id=actor.public_id if actor else "",
            archived_at=archive.archived_at.isoformat() if archive.archived_at else "",
            user=user,
            response_id=archive.original_response_id,
            status="submitted",
            quality_passed=response_data.get("quality_passed"),
            quality_flags=response_data.get("quality_flags")
            if isinstance(response_data.get("quality_flags"), dict)
            else {},
            telemetry=telemetry_data,
        )
        if fmt == "json":
            records.append(json_record)
        else:
            rows.append(csv_row)

    return records if fmt == "json" else rows


def build_runs_export(db: Session, *, include_debug: bool, fmt: ExportFormat):
    header = [
        "参与者公开ID",
        "参与者昵称",
        "调试账号",
        "会话ID",
        "对局ID",
        "模式",
        "场景键",
        "轮次",
        "对方公开ID",
        "自己选项",
        "对方选项",
        "本轮自己得分",
        "本轮对方得分",
        "累计自己得分",
        "累计对方得分",
        "自己决策毫秒",
        "对方决策毫秒",
        "自己是否超时",
        "对方是否超时",
        "自己问卷质量通过",
        "对方问卷质量通过",
        "自己理解测试通过",
        "对方理解测试通过",
        "对局完整无超时",
        "双方均为该场景首次完整对局",
        "可用于主分析",
        "会话状态",
        "轮次开始时间",
        "轮次结算时间",
    ]
    rows: list[list] = [header]
    records: list[dict] = []

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
        if not include_debug and getattr(user, "is_debug", False):
            continue
        scene_key = sess.scene.scene_key if sess.scene else ""
        rounds = sorted(sess.rounds, key=lambda r: r.round_no)
        match = (
            db.query(PvpMatch)
            .options(joinedload(PvpMatch.rounds))
            .filter(
                or_(
                    PvpMatch.session_a_id == sess.id,
                    PvpMatch.session_b_id == sess.id,
                )
            )
            .first()
        )
        opponent_id = None
        if match is not None:
            opponent_id = (
                match.user_b_id if match.session_a_id == sess.id else match.user_a_id
            )
        opponent = db.get(User, opponent_id) if opponent_id else None
        opponent_session_id = None
        if match is not None:
            opponent_session_id = (
                match.session_b_id if match.session_a_id == sess.id else match.session_a_id
            )
        my_quality = survey_quality_passed_for_user(db, user.id)
        opponent_quality = (
            survey_quality_passed_for_user(db, opponent_id) if opponent_id else None
        )
        my_comprehension = (
            db.query(GameComprehension)
            .filter(
                GameComprehension.user_id == user.id,
                GameComprehension.experiment_id == sess.experiment_id,
            )
            .first()
        )
        opponent_comprehension = (
            db.query(GameComprehension)
            .filter(
                GameComprehension.user_id == opponent_id,
                GameComprehension.experiment_id == sess.experiment_id,
            )
            .first()
            if opponent_id
            else None
        )
        my_understood = bool(my_comprehension and my_comprehension.passed)
        opponent_understood = bool(
            opponent_comprehension and opponent_comprehension.passed
        )
        pvp_rounds = {
            round_row.round_no: round_row for round_row in (match.rounds if match else [])
        }
        complete_without_timeout = bool(
            match is not None
            and sess.mode == "matched"
            and sess.status == "finished"
            and match.status == "finished"
            and len(pvp_rounds) == match.rounds_total
            and all(
                row.status == "resolved"
                and not row.a_timed_out
                and not row.b_timed_out
                for row in pvp_rounds.values()
            )
        )
        first_my_session_id = (
            db.query(GameSession.id)
            .filter(
                GameSession.user_id == user.id,
                GameSession.experiment_id == sess.experiment_id,
                GameSession.scene_id == sess.scene_id,
                GameSession.mode == "matched",
                GameSession.status == "finished",
            )
            .order_by(GameSession.id.asc())
            .scalar()
        )
        first_opponent_session_id = None
        if opponent_id:
            first_opponent_session_id = (
                db.query(GameSession.id)
                .filter(
                    GameSession.user_id == opponent_id,
                    GameSession.experiment_id == sess.experiment_id,
                    GameSession.scene_id == sess.scene_id,
                    GameSession.mode == "matched",
                    GameSession.status == "finished",
                )
                .order_by(GameSession.id.asc())
                .scalar()
            )
        first_completed_for_both = bool(
            match is not None
            and sess.id == first_my_session_id
            and opponent_session_id == first_opponent_session_id
        )
        analysis_eligible = bool(
            complete_without_timeout
            and first_completed_for_both
            and my_quality is True
            and opponent_quality is True
            and my_understood
            and opponent_understood
        )

        def append_round(
            *,
            round_no: Any,
            my_choice: Any,
            opponent_choice: Any,
            my_points: Any,
            opponent_points: Any,
            my_timed_out: Any,
            opponent_timed_out: Any,
            my_decision_ms: Any,
            opponent_decision_ms: Any,
            started_at: Any,
            resolved_at: Any,
        ) -> None:
            if fmt == "json":
                records.append(
                    {
                        "user_public_id": user.public_id,
                        "nickname": user.nickname,
                        "is_debug": bool(getattr(user, "is_debug", False)),
                        "session_id": sess.id,
                        "match_id": match.id if match else None,
                        "mode": sess.mode,
                        "scene_key": scene_key,
                        "round_no": round_no if round_no != "" else None,
                        "opponent_public_id": opponent.public_id if opponent else None,
                        "my_choice": my_choice if my_choice != "" else None,
                        "opponent_choice": opponent_choice if opponent_choice != "" else None,
                        "my_points": my_points if my_points != "" else None,
                        "opponent_points": opponent_points if opponent_points != "" else None,
                        "session_my_score": sess.my_score,
                        "session_opponent_score": sess.opponent_score,
                        "my_decision_ms": my_decision_ms if my_decision_ms != "" else None,
                        "opponent_decision_ms": opponent_decision_ms
                        if opponent_decision_ms != ""
                        else None,
                        "my_timed_out": my_timed_out if my_timed_out != "" else None,
                        "opponent_timed_out": opponent_timed_out
                        if opponent_timed_out != ""
                        else None,
                        "my_survey_quality_passed": my_quality,
                        "opponent_survey_quality_passed": opponent_quality,
                        "my_comprehension_passed": my_understood,
                        "opponent_comprehension_passed": opponent_understood,
                        "game_quality_passed": complete_without_timeout,
                        "first_completed_for_both": first_completed_for_both,
                        "analysis_eligible": analysis_eligible,
                        "session_status": sess.status,
                        "round_started_at": started_at if started_at != "" else None,
                        "round_resolved_at": resolved_at if resolved_at != "" else None,
                    }
                )
            else:
                rows.append(
                    [
                        user.public_id,
                        user.nickname,
                        _bool_zh(getattr(user, "is_debug", False)),
                        sess.id,
                        match.id if match else "",
                        sess.mode,
                        scene_key,
                        round_no,
                        opponent.public_id if opponent else "",
                        my_choice,
                        opponent_choice,
                        my_points,
                        opponent_points,
                        sess.my_score,
                        sess.opponent_score,
                        my_decision_ms,
                        opponent_decision_ms,
                        _bool_zh(my_timed_out) if my_timed_out != "" else "",
                        _bool_zh(opponent_timed_out) if opponent_timed_out != "" else "",
                        _bool_zh(my_quality),
                        _bool_zh(opponent_quality),
                        _bool_zh(my_understood),
                        _bool_zh(opponent_understood),
                        _bool_zh(complete_without_timeout),
                        _bool_zh(first_completed_for_both),
                        _bool_zh(analysis_eligible),
                        sess.status,
                        started_at,
                        resolved_at,
                    ]
                )

        if not rounds:
            append_round(
                round_no="",
                my_choice="",
                opponent_choice="",
                my_points="",
                opponent_points="",
                my_timed_out="",
                opponent_timed_out="",
                my_decision_ms="",
                opponent_decision_ms="",
                started_at="",
                resolved_at="",
            )
            continue

        for r in rounds:
            pvp_round = pvp_rounds.get(r.round_no)
            is_a = bool(match and match.session_a_id == sess.id)
            my_decision_ms = ""
            opponent_decision_ms = ""
            if match is not None and opponent_id is not None:
                my_decision_ms = (
                    db.query(PvpDecisionTelemetry.decision_ms)
                    .filter(
                        PvpDecisionTelemetry.match_id == match.id,
                        PvpDecisionTelemetry.round_no == r.round_no,
                        PvpDecisionTelemetry.user_id == sess.user_id,
                    )
                    .scalar()
                    or ""
                )
                opponent_decision_ms = (
                    db.query(PvpDecisionTelemetry.decision_ms)
                    .filter(
                        PvpDecisionTelemetry.match_id == match.id,
                        PvpDecisionTelemetry.round_no == r.round_no,
                        PvpDecisionTelemetry.user_id == opponent_id,
                    )
                    .scalar()
                    or ""
                )
            append_round(
                round_no=r.round_no,
                my_choice=r.my_choice,
                opponent_choice=r.opponent_choice,
                my_points=r.my_points,
                opponent_points=r.opponent_points,
                my_timed_out=(
                    pvp_round.a_timed_out if is_a else pvp_round.b_timed_out
                )
                if pvp_round
                else "",
                opponent_timed_out=(
                    pvp_round.b_timed_out if is_a else pvp_round.a_timed_out
                )
                if pvp_round
                else "",
                my_decision_ms=my_decision_ms,
                opponent_decision_ms=opponent_decision_ms,
                started_at=pvp_round.started_at.isoformat()
                if pvp_round and pvp_round.started_at
                else "",
                resolved_at=pvp_round.resolved_at.isoformat()
                if pvp_round and pvp_round.resolved_at
                else "",
            )

    return records if fmt == "json" else rows


def export_dataset(
    db: Session,
    admin: User,
    *,
    kind: ExportKind,
    fmt: ExportFormat,
    filename: str | None = None,
) -> Response:
    include_debug = is_sudo(admin)
    builders = {
        "users": build_users_export,
        "survey-answers": build_survey_answers_export,
        "survey-quality": build_survey_quality_export,
        "runs": build_runs_export,
    }
    data = builders[kind](db, include_debug=include_debug, fmt=fmt)
    return file_response(
        kind=kind,
        fmt=fmt,
        rows_or_records=data,
        filename=filename,
        include_debug=include_debug,
    )
