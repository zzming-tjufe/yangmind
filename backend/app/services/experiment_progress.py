"""参与者实验进度的跨模块判断。"""

from sqlalchemy.orm import Session

from app.data.stag_hunt_seed import STAG_HUNT_CODE
from app.models.game import Experiment, ExperimentScene, GameSession


def personality_feedback_unlocked(db: Session, user_id: int) -> bool:
    """全部必做场景完成后才展示人格反馈，避免人格标签影响博弈选择。"""
    experiment = (
        db.query(Experiment)
        .filter(Experiment.code == STAG_HUNT_CODE)
        .first()
    )
    if experiment is None:
        return False
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
    if not required_scene_ids:
        return False
    finished_scene_ids = {
        scene_id
        for (scene_id,) in db.query(GameSession.scene_id)
        .filter(
            GameSession.user_id == user_id,
            GameSession.experiment_id == experiment.id,
            GameSession.status == "finished",
            GameSession.scene_id.in_(required_scene_ids),
        )
        .all()
    }
    return required_scene_ids.issubset(finished_scene_ids)
