import asyncio
import csv
import io
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.auth import _public_id_for_user
from app.core.database import Base
from app.data.bfi44_seed import BFI44_ITEMS
from app.core.security import (
    access_token_matches_password,
    create_access_token,
    decode_access_token,
    hash_password,
)
from app.models.game import Experiment, ExperimentScene, GameComprehension, GameRound, GameSession
from app.models.match import PvpDecisionTelemetry, PvpMatch, PvpRound
from app.models.survey import (
    PersonalityScore,
    SurveyAnswer,
    SurveyInstrument,
    SurveyItem,
    SurveyQualityTelemetry,
    SurveyResponse,
    SurveyRetakeArchive,
)
from app.models.user import User
from app.schemas.survey import SaveAnswersRequest, SubmitSurveyRequest
from app.services.bfi_scoring import check_quality
from app.services.db_fixes import repair_pvp_timeout_choices
from app.services.experiment_progress import personality_feedback_unlocked
from app.services.game_comprehension import submit_comprehension
from app.services.pvp import (
    _mirror_round_to_sessions,
    claim_waiting_match,
    create_sessions_for_match,
    maybe_resolve_round,
    start_round,
)
from app.api.pvp import (
    PvpChoiceBody,
    _require_survey as require_pvp_survey,
    join_queue,
    submit_choice,
)
from app.api.admin import allow_survey_retake, export_rounds, export_surveys
from app.api.survey import submit as submit_survey


class _FakeSession:
    def __init__(self, objects):
        self.objects = objects
        self.added = []

    def get(self, _model, object_id):
        return self.objects.get(object_id)

    def add(self, value):
        self.added.append(value)


class EdgeRegressionTests(unittest.TestCase):
    def test_survey_submission_persists_quality_telemetry(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user = User(
                public_id="U-TELEMETRY",
                email="telemetry@example.com",
                password_hash="x",
                nickname="telemetry",
            )
            instrument = SurveyInstrument(
                code="BFI-44",
                version="test",
                title="BFI-44",
                item_count=44,
            )
            db.add_all([user, instrument])
            db.flush()
            for item in BFI44_ITEMS:
                db.add(
                    SurveyItem(
                        instrument_id=instrument.id,
                        item_no=item["item_no"],
                        stem=item["stem"],
                        dimension=item["dimension"],
                        reverse_scored=item["reverse_scored"],
                        sort_order=item["item_no"],
                    )
                )
            response = SurveyResponse(
                user_id=user.id,
                instrument_id=instrument.id,
                instrument_version="test",
                status="in_progress",
                started_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=6),
            )
            db.add(response)
            db.flush()
            for item in BFI44_ITEMS:
                db.add(
                    SurveyAnswer(
                        response_id=response.id,
                        item_no=item["item_no"],
                        value=2 if item["reverse_scored"] else 4,
                    )
                )
            db.commit()

            submit_survey(
                SubmitSurveyRequest(
                    attention_answers=[
                        {"check_id": "attention_1", "value": 4},
                        {"check_id": "attention_2", "value": 2},
                    ],
                    diligence_answers=[
                        {"check_id": "diligence_read", "value": 5},
                        {"check_id": "diligence_authentic", "value": 5},
                        {"check_id": "diligence_technical", "value": 1},
                    ],
                    page_timings_seconds={"1": 90, "2": 90, "3": 90, "4": 90},
                    blur_count=2,
                    device_token="test-device",
                ),
                db=db,
                current_user=user,
            )

            telemetry = db.query(SurveyQualityTelemetry).one()
            self.assertEqual(telemetry.attention_answers["attention_1"], 4)
            self.assertEqual(telemetry.page_timings_seconds["4"], 90.0)
            self.assertEqual(telemetry.blur_count, 2)
            self.assertEqual(telemetry.soft_flags, [])

    def test_pvp_choice_records_decision_time(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user_a = User(public_id="U-DA", email="da@example.com", password_hash="x", nickname="a")
            user_b = User(public_id="U-DB", email="db@example.com", password_hash="x", nickname="b")
            experiment = Experiment(code="decision-time", title="test", rounds_per_scene=1)
            db.add_all([user_a, user_b, experiment])
            db.flush()
            scene = ExperimentScene(
                experiment_id=experiment.id,
                scene_key="task",
                no="01",
                title="task",
                short_desc="task",
                option_a="A",
                option_b="B",
                option_a_text="A",
                option_b_text="B",
            )
            db.add(scene)
            db.flush()
            match = PvpMatch(
                experiment_id=experiment.id,
                scene_id=scene.id,
                status="playing",
                user_a_id=user_a.id,
                user_b_id=user_b.id,
                rounds_total=1,
                current_round=1,
                round_deadline=datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=15),
            )
            db.add(match)
            db.flush()
            db.add(
                PvpRound(
                    match_id=match.id,
                    round_no=1,
                    status="open",
                    started_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=2),
                )
            )
            db.commit()

            submit_choice(
                match.id,
                PvpChoiceBody(choice="A", round_no=1),
                db=db,
                current_user=user_a,
            )

            decision = db.query(PvpDecisionTelemetry).one()
            self.assertEqual(decision.user_id, user_a.id)
            self.assertGreaterEqual(decision.decision_ms, 1500)

    def test_csv_exports_keep_every_row_aligned_with_its_header(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            admin = User(
                public_id="A-CSV",
                email="admin-csv@example.com",
                password_hash="x",
                nickname="admin",
                role="super_admin",
            )
            user = User(
                public_id="U-CSV",
                email="csv@example.com",
                password_hash="x",
                nickname="csv",
            )
            instrument = SurveyInstrument(
                code="BFI-44",
                version="test",
                title="BFI-44",
                item_count=44,
            )
            experiment = Experiment(code="csv-export", title="test")
            db.add_all([admin, user, instrument, experiment])
            db.flush()
            scene = ExperimentScene(
                experiment_id=experiment.id,
                scene_key="task",
                no="01",
                title="task",
                short_desc="task",
                option_a="A",
                option_b="B",
                option_a_text="A",
                option_b_text="B",
            )
            db.add(scene)
            db.flush()
            response = SurveyResponse(
                user_id=user.id,
                instrument_id=instrument.id,
                instrument_version="test",
                status="submitted",
                quality_passed=True,
            )
            db.add(response)
            db.flush()
            db.add_all(
                [
                    SurveyAnswer(response_id=response.id, item_no=1, value=4),
                    GameSession(
                        user_id=user.id,
                        experiment_id=experiment.id,
                        scene_id=scene.id,
                        status="playing",
                    ),
                ]
            )
            db.commit()

            async def read_rows(streaming_response):
                chunks = []
                async for chunk in streaming_response.body_iterator:
                    chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
                text = b"".join(chunks).decode("utf-8-sig")
                return list(csv.reader(io.StringIO(text)))

            survey_rows = asyncio.run(read_rows(export_surveys(db=db, _=admin)))
            round_rows = asyncio.run(read_rows(export_rounds(db=db, _=admin)))
            self.assertTrue(all(len(row) == len(survey_rows[0]) for row in survey_rows))
            self.assertTrue(all(len(row) == len(round_rows[0]) for row in round_rows))
            self.assertEqual(survey_rows[1][0], "current")

    def test_admin_retake_archives_original_and_reopens_blank_draft(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            admin = User(
                public_id="A-RETAKE",
                email="admin-retake@example.com",
                password_hash="x",
                nickname="admin",
                role="super_admin",
            )
            user = User(
                public_id="U-RETAKE",
                email="retake@example.com",
                password_hash="x",
                nickname="retake",
            )
            instrument = SurveyInstrument(
                code="BFI-44",
                version="test",
                title="BFI-44",
                item_count=44,
            )
            db.add_all([admin, user, instrument])
            db.flush()
            response = SurveyResponse(
                user_id=user.id,
                instrument_id=instrument.id,
                instrument_version="test",
                status="submitted",
                quality_passed=False,
                quality_flags={"attention_failed": True},
            )
            db.add(response)
            db.flush()
            db.add_all(
                [
                    SurveyAnswer(response_id=response.id, item_no=1, value=2),
                    PersonalityScore(
                        user_id=user.id,
                        response_id=response.id,
                        e=3,
                        a=3,
                        c=3,
                        n=3,
                        o=3,
                        summary_label="test",
                    ),
                ]
            )
            db.commit()

            result = allow_survey_retake(user.id, db=db, admin=admin)

            db.refresh(response)
            archive = db.query(SurveyRetakeArchive).one()
            self.assertTrue(result["ok"])
            self.assertEqual(result["retake_count"], 1)
            self.assertEqual(response.status, "in_progress")
            self.assertIsNone(response.quality_passed)
            self.assertEqual(db.query(SurveyAnswer).count(), 0)
            self.assertEqual(db.query(PersonalityScore).count(), 0)
            self.assertEqual(archive.response_snapshot["answers"], [{"item_no": 1, "value": 2}])
            self.assertFalse(archive.response_snapshot["response"]["quality_passed"])

    def test_admin_retake_is_blocked_after_game_participation(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            admin = User(
                public_id="A-BLOCK",
                email="admin-block@example.com",
                password_hash="x",
                nickname="admin",
                role="super_admin",
            )
            user = User(
                public_id="U-BLOCK",
                email="block@example.com",
                password_hash="x",
                nickname="block",
            )
            instrument = SurveyInstrument(
                code="BFI-44",
                version="test",
                title="BFI-44",
                item_count=44,
            )
            experiment = Experiment(code="retake-block", title="test")
            db.add_all([admin, user, instrument, experiment])
            db.flush()
            scene = ExperimentScene(
                experiment_id=experiment.id,
                scene_key="task",
                no="01",
                title="task",
                short_desc="task",
                option_a="A",
                option_b="B",
                option_a_text="A",
                option_b_text="B",
            )
            db.add(scene)
            db.flush()
            db.add_all(
                [
                    SurveyResponse(
                        user_id=user.id,
                        instrument_id=instrument.id,
                        instrument_version="test",
                        status="submitted",
                        quality_passed=True,
                    ),
                    GameSession(
                        user_id=user.id,
                        experiment_id=experiment.id,
                        scene_id=scene.id,
                        status="finished",
                    ),
                ]
            )
            db.commit()

            with self.assertRaises(HTTPException) as raised:
                allow_survey_retake(user.id, db=db, admin=admin)

            self.assertEqual(raised.exception.status_code, 400)
            self.assertIn("已进入博弈", raised.exception.detail)

    def test_comprehension_requires_all_correct_but_allows_learning_retry(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user = User(
                public_id="U-CHECK",
                email="check@example.com",
                password_hash="x",
                nickname="check",
            )
            experiment = Experiment(code="check", title="check")
            db.add_all([user, experiment])
            db.commit()

            first = submit_comprehension(
                db,
                user.id,
                experiment.id,
                {
                    "simultaneous": "yes",
                    "payoff_aa": "10",
                    "payoff_ab": "0",
                    "payoff_ba": "6",
                    "payoff_bb": "6",
                },
            )
            self.assertFalse(first.passed)
            self.assertEqual(first.attempts, 1)
            self.assertEqual(first.last_incorrect_ids, ["simultaneous"])

            second = submit_comprehension(
                db,
                user.id,
                experiment.id,
                {
                    "simultaneous": "no",
                    "payoff_aa": "10",
                    "payoff_ab": "0",
                    "payoff_ba": "6",
                    "payoff_bb": "6",
                },
            )
            self.assertTrue(second.passed)
            self.assertEqual(second.attempts, 2)
            self.assertEqual(second.last_incorrect_ids, [])

    def test_pvp_requires_a_submitted_quality_passed_survey(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user = User(
                public_id="U-QUALITY",
                email="quality@example.com",
                password_hash="x",
                nickname="quality",
            )
            instrument = SurveyInstrument(
                code="BFI-44",
                version="test",
                title="BFI-44",
                item_count=44,
            )
            db.add_all([user, instrument])
            db.flush()
            response = SurveyResponse(
                user_id=user.id,
                instrument_id=instrument.id,
                instrument_version="test",
                status="submitted",
                quality_passed=False,
            )
            db.add(response)
            db.commit()

            with self.assertRaises(HTTPException) as raised:
                require_pvp_survey(db, user)
            self.assertEqual(raised.exception.status_code, 403)

            response.quality_passed = True
            db.commit()
            require_pvp_survey(db, user)

    def test_match_queue_skips_waiting_users_with_failed_surveys(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            users = [
                User(
                    public_id=f"U-{index}",
                    email=f"u{index}@example.com",
                    password_hash="x",
                    nickname=f"u{index}",
                )
                for index in range(1, 4)
            ]
            instrument = SurveyInstrument(
                code="BFI-44",
                version="test",
                title="BFI-44",
                item_count=44,
            )
            experiment = Experiment(code="queue-test", title="test", rounds_per_scene=10)
            db.add_all([*users, instrument, experiment])
            db.flush()
            scene = ExperimentScene(
                experiment_id=experiment.id,
                scene_key="task",
                no="01",
                title="task",
                short_desc="task",
                option_a="A",
                option_b="B",
                option_a_text="A",
                option_b_text="B",
                required=True,
                enabled=True,
            )
            db.add(scene)
            db.flush()
            for user, passed in zip(users, [False, True, True]):
                db.add(
                    SurveyResponse(
                        user_id=user.id,
                        instrument_id=instrument.id,
                        instrument_version="test",
                        status="submitted",
                        quality_passed=passed,
                    )
                )
            failed_match = PvpMatch(
                experiment_id=experiment.id,
                scene_id=scene.id,
                status="waiting",
                user_a_id=users[0].id,
            )
            valid_match = PvpMatch(
                experiment_id=experiment.id,
                scene_id=scene.id,
                status="waiting",
                user_a_id=users[1].id,
            )
            db.add_all([failed_match, valid_match])
            db.commit()

            claimed = claim_waiting_match(
                db, scene_id=scene.id, user_id=users[2].id
            )

            self.assertIsNotNone(claimed)
            self.assertEqual(claimed.id, valid_match.id)
            self.assertEqual(failed_match.status, "waiting")

    def test_completed_experiment_cannot_be_matched_again_in_another_scene(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user = User(
                public_id="U-ONCE",
                email="once@example.com",
                password_hash="x",
                nickname="once",
            )
            instrument = SurveyInstrument(
                code="BFI-44",
                version="test",
                title="BFI-44",
                item_count=44,
            )
            experiment = Experiment(code="stag_hunt", title="test", rounds_per_scene=10)
            db.add_all([user, instrument, experiment])
            db.flush()
            scene = ExperimentScene(
                experiment_id=experiment.id,
                scene_key="task",
                no="01",
                title="task",
                short_desc="task",
                option_a="A",
                option_b="B",
                option_a_text="A",
                option_b_text="B",
                required=True,
                enabled=True,
            )
            other_scene = ExperimentScene(
                experiment_id=experiment.id,
                scene_key="travel",
                no="02",
                title="travel",
                short_desc="travel",
                option_a="A",
                option_b="B",
                option_a_text="A",
                option_b_text="B",
                required=True,
                enabled=True,
            )
            db.add_all([scene, other_scene])
            db.flush()
            db.add_all(
                [
                    SurveyResponse(
                        user_id=user.id,
                        instrument_id=instrument.id,
                        instrument_version="test",
                        status="submitted",
                        quality_passed=True,
                    ),
                    GameSession(
                        user_id=user.id,
                        experiment_id=experiment.id,
                        scene_id=scene.id,
                        mode="matched",
                        status="finished",
                    ),
                    GameComprehension(
                        user_id=user.id,
                        experiment_id=experiment.id,
                        attempts=1,
                        passed=True,
                    ),
                ]
            )
            db.commit()

            with self.assertRaises(HTTPException) as raised:
                join_queue("travel", db=db, current_user=user)

            self.assertEqual(raised.exception.status_code, 409)
            self.assertIn("只能参加一次", raised.exception.detail)

    def test_public_id_comes_from_database_id(self):
        self.assertEqual(_public_id_for_user(1), "U-1001")
        self.assertEqual(_public_id_for_user(42), "U-1042")
        # 注册占位 public_id 必须 ≤ 列宽 32
        from uuid import uuid4

        pending = f"P-{uuid4().hex[:28]}"
        self.assertLessEqual(len(pending), 32)

    def test_duplicate_survey_item_is_rejected_before_database_write(self):
        with self.assertRaises(ValidationError):
            SaveAnswersRequest.model_validate(
                {
                    "answers": [
                        {"item_no": 1, "value": 2},
                        {"item_no": 1, "value": 5},
                    ]
                }
            )

    def test_constant_answers_are_reviewed_but_do_not_fail_without_independent_signal(self):
        passed, flags = check_quality(
            {item_no: 3 for item_no in range(1, 45)},
            duration_seconds=360,
            attention_answers={"attention_1": 4, "attention_2": 2},
        )
        self.assertTrue(passed)
        self.assertEqual(flags["max_same_streak"], 44)
        self.assertEqual(flags["triggered_categories"], ["response_behavior"])
        self.assertIn("longstring", flags["response_behavior_reasons"])
        self.assertIn("low_variability", flags["response_behavior_reasons"])

    def test_constant_extreme_answers_do_not_double_count_consistency(self):
        passed, flags = check_quality(
            {item_no: 5 for item_no in range(1, 45)},
            duration_seconds=360,
            attention_answers={"attention_1": 4, "attention_2": 2},
        )
        self.assertTrue(passed)
        self.assertEqual(flags["triggered_categories"], ["response_behavior"])
        self.assertIn("inconsistent_pairs", flags["response_behavior_reasons"])

    def test_constant_answers_plus_fast_completion_fail(self):
        passed, flags = check_quality(
            {item_no: 3 for item_no in range(1, 45)},
            duration_seconds=60,
            attention_answers={"attention_1": 4, "attention_2": 2},
        )
        self.assertFalse(passed)
        self.assertEqual(
            flags["triggered_categories"],
            ["response_behavior", "very_fast"],
        )

    def test_quality_check_passes_consistent_attentive_answers(self):
        answers = {
            item["item_no"]: 2 if item["reverse_scored"] else 4
            for item in BFI44_ITEMS
        }
        passed, flags = check_quality(
            answers,
            duration_seconds=360,
            attention_answers={"attention_1": 4, "attention_2": 2},
        )
        self.assertTrue(passed)
        self.assertEqual(flags["triggered_categories"], [])

    def test_one_quality_signal_is_review_only(self):
        answers = {
            item["item_no"]: 2 if item["reverse_scored"] else 4
            for item in BFI44_ITEMS
        }
        passed, flags = check_quality(
            answers,
            duration_seconds=60,
            attention_answers={"attention_1": 4, "attention_2": 2},
        )
        self.assertTrue(passed)
        self.assertTrue(flags["review_recommended"])
        self.assertEqual(flags["triggered_categories"], ["very_fast"])

    def test_two_independent_quality_signals_fail(self):
        answers = {
            item["item_no"]: 2 if item["reverse_scored"] else 4
            for item in BFI44_ITEMS
        }
        passed, flags = check_quality(
            answers,
            duration_seconds=60,
            attention_answers={"attention_1": 1, "attention_2": 2},
        )
        self.assertFalse(passed)
        self.assertEqual(
            flags["triggered_categories"],
            ["very_fast", "attention_check"],
        )

    def test_personality_feedback_unlocks_only_after_both_fixed_pair_scenes(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user = User(
                public_id="U-2001",
                email="feedback@example.com",
                password_hash="x",
                nickname="feedback",
            )
            experiment = Experiment(
                code="stag_hunt",
                title="test",
                rounds_per_scene=1,
            )
            db.add_all([user, experiment])
            db.flush()
            scenes = [
                ExperimentScene(
                    experiment_id=experiment.id,
                    scene_key=f"scene-{index}",
                    no=f"0{index}",
                    title=f"scene-{index}",
                    short_desc="test",
                    option_a="A",
                    option_b="B",
                    option_a_text="A",
                    option_b_text="B",
                    required=True,
                    enabled=True,
                )
                for index in (1, 2)
            ]
            db.add_all(scenes)
            db.flush()
            db.add(
                GameSession(
                    user_id=user.id,
                    experiment_id=experiment.id,
                    scene_id=scenes[0].id,
                    mode="matched",
                    status="finished",
                )
            )
            db.commit()
            self.assertFalse(personality_feedback_unlocked(db, user.id))

            db.add(
                GameSession(
                    user_id=user.id,
                    experiment_id=experiment.id,
                    scene_id=scenes[1].id,
                    mode="matched",
                    status="finished",
                )
            )
            db.commit()
            self.assertTrue(personality_feedback_unlocked(db, user.id))

    def test_first_scene_completion_starts_second_scene_for_the_same_pair(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            users = [
                User(
                    public_id=f"U-PAIR-{index}",
                    email=f"pair-{index}@example.com",
                    password_hash="x",
                    nickname=f"pair-{index}",
                )
                for index in (1, 2)
            ]
            experiment = Experiment(code="stag_hunt", title="test", rounds_per_scene=1)
            db.add_all([*users, experiment])
            db.flush()
            scenes = [
                ExperimentScene(
                    experiment_id=experiment.id,
                    scene_key=f"scene-{index}",
                    no=f"0{index}",
                    title=f"scene-{index}",
                    short_desc="test",
                    option_a="A",
                    option_b="B",
                    option_a_text="A",
                    option_b_text="B",
                    required=True,
                    enabled=True,
                    sort_order=index,
                )
                for index in (1, 2)
            ]
            db.add_all(scenes)
            db.flush()
            first_match = PvpMatch(
                experiment_id=experiment.id,
                scene_id=scenes[0].id,
                status="playing",
                user_a_id=users[0].id,
                user_b_id=users[1].id,
                rounds_total=1,
                current_round=1,
            )
            db.add(first_match)
            db.flush()
            create_sessions_for_match(db, first_match, scenes[0], experiment)
            round_one = start_round(db, first_match)
            round_one.choice_a = "A"
            round_one.choice_b = "A"

            maybe_resolve_round(db, first_match)
            db.commit()

            matches = db.query(PvpMatch).order_by(PvpMatch.id.asc()).all()
            self.assertEqual(len(matches), 2)
            successor = matches[1]
            self.assertEqual(successor.scene_id, scenes[1].id)
            self.assertEqual(successor.status, "playing")
            self.assertEqual(successor.user_a_id, first_match.user_a_id)
            self.assertEqual(successor.user_b_id, first_match.user_b_id)
            self.assertEqual(len(successor.rounds), 1)

    def test_password_change_invalidates_existing_token(self):
        old_hash = hash_password("old-password")
        token = create_access_token(7, old_hash)
        decoded = decode_access_token(token)
        self.assertIsNotNone(decoded)
        user_id, version = decoded
        self.assertEqual(user_id, 7)
        self.assertTrue(access_token_matches_password(version, old_hash))
        self.assertFalse(
            access_token_matches_password(version, hash_password("new-password"))
        )

    def test_pvp_timeout_is_mirrored_as_timeout_not_choice_b(self):
        session_a = SimpleNamespace(id=11, status="playing", my_score=0, opponent_score=0)
        session_b = SimpleNamespace(id=12, status="playing", my_score=0, opponent_score=0)
        db = _FakeSession({11: session_a, 12: session_b})
        match = SimpleNamespace(
            session_a_id=11,
            session_b_id=12,
            score_a=3,
            score_b=0,
        )
        round_result = SimpleNamespace(
            round_no=1,
            choice_a="A",
            choice_b=None,
            points_a=3,
            points_b=0,
        )

        _mirror_round_to_sessions(db, match, round_result)

        self.assertEqual(len(db.added), 2)
        self.assertTrue(all(isinstance(item, GameRound) for item in db.added))
        self.assertEqual(db.added[0].my_choice, "A")
        self.assertEqual(db.added[0].opponent_choice, "T")
        self.assertEqual(db.added[1].my_choice, "T")
        self.assertEqual(db.added[1].opponent_choice, "A")

    def test_historical_pvp_timeout_choices_are_repaired(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user_a = User(
                public_id="U-1001",
                email="a@example.com",
                password_hash="x",
                nickname="a",
            )
            user_b = User(
                public_id="U-1002",
                email="b@example.com",
                password_hash="x",
                nickname="b",
            )
            experiment = Experiment(code="test", title="test", rounds_per_scene=1)
            db.add_all([user_a, user_b, experiment])
            db.flush()
            scene = ExperimentScene(
                experiment_id=experiment.id,
                scene_key="scene",
                no="01",
                title="scene",
                short_desc="scene",
                option_a="A",
                option_b="B",
                option_a_text="A",
                option_b_text="B",
            )
            db.add(scene)
            db.flush()
            session_a = GameSession(
                user_id=user_a.id,
                experiment_id=experiment.id,
                scene_id=scene.id,
                mode="matched",
            )
            session_b = GameSession(
                user_id=user_b.id,
                experiment_id=experiment.id,
                scene_id=scene.id,
                mode="matched",
            )
            db.add_all([session_a, session_b])
            db.flush()
            match = PvpMatch(
                experiment_id=experiment.id,
                scene_id=scene.id,
                status="playing",
                user_a_id=user_a.id,
                user_b_id=user_b.id,
                session_a_id=session_a.id,
                session_b_id=session_b.id,
                rounds_total=1,
            )
            db.add(match)
            db.flush()
            db.add(
                PvpRound(
                    match_id=match.id,
                    round_no=1,
                    status="resolved",
                    choice_a="A",
                    choice_b=None,
                    b_timed_out=True,
                    points_a=3,
                    points_b=0,
                )
            )
            db.add_all(
                [
                    GameRound(
                        session_id=session_a.id,
                        round_no=1,
                        my_choice="A",
                        opponent_choice="B",
                        my_points=3,
                        opponent_points=0,
                    ),
                    GameRound(
                        session_id=session_b.id,
                        round_no=1,
                        my_choice="B",
                        opponent_choice="A",
                        my_points=0,
                        opponent_points=3,
                    ),
                ]
            )
            db.commit()

            self.assertEqual(repair_pvp_timeout_choices(db), 2)
            repaired = db.query(GameRound).order_by(GameRound.session_id).all()
            self.assertEqual((repaired[0].my_choice, repaired[0].opponent_choice), ("A", "T"))
            self.assertEqual((repaired[1].my_choice, repaired[1].opponent_choice), ("T", "A"))


if __name__ == "__main__":
    unittest.main()
