from pydantic import BaseModel, EmailStr, Field


class LeaderboardEntry(BaseModel):
    rank: int
    nickname: str
    public_id: str
    sessions_count: int
    personality_summary: str
    total_score: int


class LeaderboardOut(BaseModel):
    period: str = "all"
    items: list[LeaderboardEntry]


class AdminUserRow(BaseModel):
    id: int
    nickname: str
    public_id: str
    email: EmailStr
    role: str = "participant"
    total_score: int
    sessions_count: int
    personality_summary: str
    survey_status: str
    quality_passed: bool | None = None
    has_personality: bool
    status: str = "active"
    can_retake_survey: bool = False
    retake_count: int = 0
    retake_block_reason: str | None = None
    has_submitted_survey: bool = False
    quality_review_status: str | None = None
    quality_soft_flags: list[str] = Field(default_factory=list)
    quality_hard_exclusion: bool = False
    is_debug: bool = False


class AdminUsersOut(BaseModel):
    total: int
    items: list[AdminUserRow]


class DimensionDetail(BaseModel):
    code: str
    name: str
    english: str
    score: float
    general: str
    band_text: str


class AdminPersonalityOut(BaseModel):
    user_id: int
    nickname: str
    public_id: str
    summary_label: str
    scores: dict[str, float]
    dimensions: list[DimensionDetail]
    quality_passed: bool | None = None


class AdminStatsOut(BaseModel):
    total_users: int
    survey_completion_rate: float
    valid_rounds: int
    avg_coop_rate: float
