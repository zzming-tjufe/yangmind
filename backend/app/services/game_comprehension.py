from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.game import GameComprehension


COMPREHENSION_QUESTIONS = [
    {
        "question_id": "simultaneous",
        "prompt": "每一轮做选择时，你能否提前看到对方本轮的选择？",
        "options": [
            {"value": "no", "label": "不能，双方同时独立选择"},
            {"value": "yes", "label": "能，看到对方选择后再决定"},
        ],
    },
    {
        "question_id": "payoff_aa",
        "prompt": "如果你和对方本轮都选择 A，你本轮获得多少分？",
        "options": [
            {"value": "10", "label": "10 分"},
            {"value": "6", "label": "6 分"},
            {"value": "0", "label": "0 分"},
        ],
    },
    {
        "question_id": "payoff_ab",
        "prompt": "如果你选择 A、对方选择 B，你本轮获得多少分？",
        "options": [
            {"value": "10", "label": "10 分"},
            {"value": "6", "label": "6 分"},
            {"value": "0", "label": "0 分"},
        ],
    },
    {
        "question_id": "payoff_ba",
        "prompt": "如果你选择 B、对方选择 A，你本轮获得多少分？",
        "options": [
            {"value": "10", "label": "10 分"},
            {"value": "6", "label": "6 分"},
            {"value": "0", "label": "0 分"},
        ],
    },
    {
        "question_id": "payoff_bb",
        "prompt": "如果你和对方本轮都选择 B，你本轮获得多少分？",
        "options": [
            {"value": "10", "label": "10 分"},
            {"value": "6", "label": "6 分"},
            {"value": "0", "label": "0 分"},
        ],
    },
]

CORRECT_ANSWERS = {
    "simultaneous": "no",
    "payoff_aa": "10",
    "payoff_ab": "0",
    "payoff_ba": "6",
    "payoff_bb": "6",
}


def get_comprehension(
    db: Session, user_id: int, experiment_id: int
) -> GameComprehension | None:
    return (
        db.query(GameComprehension)
        .filter(
            GameComprehension.user_id == user_id,
            GameComprehension.experiment_id == experiment_id,
        )
        .first()
    )


def comprehension_passed(db: Session, user_id: int, experiment_id: int) -> bool:
    row = get_comprehension(db, user_id, experiment_id)
    return bool(row and row.passed)


def submit_comprehension(
    db: Session,
    user_id: int,
    experiment_id: int,
    answers: dict[str, str],
) -> GameComprehension:
    incorrect = [
        question_id
        for question_id, expected in CORRECT_ANSWERS.items()
        if answers.get(question_id) != expected
    ]
    row = get_comprehension(db, user_id, experiment_id)
    if row is None:
        row = GameComprehension(
            user_id=user_id,
            experiment_id=experiment_id,
            attempts=0,
            passed=False,
        )
        db.add(row)
    if not row.passed:
        row.attempts = (row.attempts or 0) + 1
        row.last_incorrect_ids = incorrect
        if not incorrect:
            row.passed = True
            row.passed_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return row
