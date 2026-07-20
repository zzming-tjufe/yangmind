from pydantic import BaseModel, Field


class SceneOut(BaseModel):
    scene_key: str
    no: str
    title: str
    short_desc: str
    option_a: str
    option_b: str
    option_a_text: str
    option_b_text: str
    required: bool
    completed: bool
    best_score: int | None = None

    model_config = {"from_attributes": True}


class StagHuntProgressOut(BaseModel):
    experiment_code: str
    title: str
    rounds_per_scene: int
    unlock_games: bool
    survey_done: bool = False
    survey_quality_failed: bool = False
    experiment_status: str = "active"
    done_count: int
    required_count: int
    all_done: bool
    scenes: list[SceneOut]
    payoff_matrix: dict = Field(
        default_factory=lambda: {
            "AA": "10 / 10",
            "AB": "0 / 6",
            "BA": "6 / 0",
            "BB": "6 / 6",
            "note": "斜线前为你的得分，斜线后为对方得分",
        }
    )


class RoundOut(BaseModel):
    round_no: int
    my_choice: str
    opponent_choice: str
    my_points: int
    opponent_points: int

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: int
    scene_key: str
    status: str
    current_round: int
    rounds_total: int
    my_score: int
    opponent_score: int
    last_round: RoundOut | None = None
    history: list[RoundOut] = Field(default_factory=list)
    experiment_all_done: bool = False

    model_config = {"from_attributes": True}


class PlayRoundRequest(BaseModel):
    choice: str = Field(pattern="^[ABab]$")
