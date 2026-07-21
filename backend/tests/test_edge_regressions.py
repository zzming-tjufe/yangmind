from types import SimpleNamespace
import unittest

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
from app.models.game import Experiment, ExperimentScene, GameRound, GameSession
from app.models.match import PvpMatch, PvpRound
from app.models.user import User
from app.schemas.survey import SaveAnswersRequest
from app.services.bfi_scoring import check_quality
from app.services.db_fixes import repair_pvp_timeout_choices
from app.services.experiment_progress import personality_feedback_unlocked
from app.services.pvp import _mirror_round_to_sessions


class _FakeSession:
    def __init__(self, objects):
        self.objects = objects
        self.added = []

    def get(self, _model, object_id):
        return self.objects.get(object_id)

    def add(self, value):
        self.added.append(value)


class EdgeRegressionTests(unittest.TestCase):
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

    def test_constant_answers_fail_quality_check(self):
        passed, flags = check_quality({item_no: 3 for item_no in range(1, 45)})
        self.assertFalse(passed)
        self.assertEqual(flags["max_same_streak"], 44)

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

    def test_personality_feedback_waits_for_all_required_scenes(self):
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
                    status="finished",
                )
            )
            db.commit()
            finished_scene_ids = {
                scene_id
                for (scene_id,) in db.query(GameSession.scene_id)
                .filter(
                    GameSession.user_id == user.id,
                    GameSession.status == "finished",
                )
                .all()
            }
            self.assertEqual(finished_scene_ids, {scenes[0].id, scenes[1].id})
            required_scene_ids = {
                scene_id
                for (scene_id,) in db.query(ExperimentScene.id)
                .filter(
                    ExperimentScene.experiment_id == experiment.id,
                    ExperimentScene.enabled.is_(True),
                    ExperimentScene.required.is_(True),
                )
                .all()
            }
            self.assertEqual(required_scene_ids, finished_scene_ids)
            self.assertTrue(personality_feedback_unlocked(db, user.id))

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
