from pydantic import BaseModel, Field, model_validator


class SurveyItemOut(BaseModel):
    item_no: int
    stem: str
    # 作答时不告诉前端哪题反向，避免诱导；计分只在服务端做
    sort_order: int

    model_config = {"from_attributes": True}


class SurveyInstrumentOut(BaseModel):
    code: str
    version: str
    title: str
    item_count: int
    scale_hint: str = "1 = 非常不同意 · 2 = 比较不同意 · 3 = 中立 · 4 = 比较同意 · 5 = 非常同意"
    items: list[SurveyItemOut]


class AnswerItem(BaseModel):
    item_no: int = Field(ge=1, le=44)
    value: int = Field(ge=1, le=5)


class SaveAnswersRequest(BaseModel):
    answers: list[AnswerItem] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_item_numbers(self):
        item_numbers = [answer.item_no for answer in self.answers]
        if len(item_numbers) != len(set(item_numbers)):
            raise ValueError("同一次保存请求中不能包含重复题号")
        return self


class PersonalityScoreOut(BaseModel):
    e: float
    a: float
    c: float
    n: float
    o: float
    summary_label: str

    model_config = {"from_attributes": True}


class MyResponseOut(BaseModel):
    status: str  # none | in_progress | submitted
    answered_count: int = 0
    answers: dict[str, int] = Field(default_factory=dict)  # {"1": 4, ...}
    personality: PersonalityScoreOut | None = None
    quality_passed: bool | None = None
    unlock_games: bool = False
