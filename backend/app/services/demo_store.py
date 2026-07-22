"""管理员演示模式：内存态，不写正式业务表，不进入导出。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DemoSurveyState:
    answers: dict[int, int] = field(default_factory=dict)
    status: str = "none"  # none | in_progress | submitted
    personality: dict[str, Any] | None = None
    quality_passed: bool | None = None
    quality_flags: dict[str, Any] | None = None


@dataclass
class DemoRound:
    round_no: int
    my_choice: str
    opponent_choice: str
    my_points: int
    opponent_points: int


@dataclass
class DemoSession:
    id: int
    scene_key: str
    scene_title: str
    rounds_total: int
    status: str = "playing"
    current_round: int = 1
    my_score: int = 0
    opponent_score: int = 0
    history: list[DemoRound] = field(default_factory=list)
    rng_seed: int = 0


@dataclass
class DemoUserStore:
    survey: DemoSurveyState = field(default_factory=DemoSurveyState)
    sessions: dict[int, DemoSession] = field(default_factory=dict)
    completed_scenes: set[str] = field(default_factory=set)
    next_session_id: int = 1
    updated_at: float = field(default_factory=time.time)


_lock = threading.Lock()
_stores: dict[int, DemoUserStore] = {}


def get_store(user_id: int) -> DemoUserStore:
    with _lock:
        store = _stores.get(user_id)
        if store is None:
            store = DemoUserStore()
            _stores[user_id] = store
        store.updated_at = time.time()
        return store


def reset_store(user_id: int) -> DemoUserStore:
    with _lock:
        store = DemoUserStore()
        _stores[user_id] = store
        return store
