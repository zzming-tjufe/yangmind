"""BFI-44 计分与简易质量检查。"""

from __future__ import annotations

from statistics import pstdev

DIMENSION_NAMES = {
    "E": "外向",
    "A": "宜人",
    "C": "尽责",
    "N": "情绪敏感",
    "O": "开放",
}

QUALITY_RULE_VERSION = "2026-07-v2"

# 独立注意力检测题，不参与 BFI-44 计分，也不改变标准题序。
ATTENTION_CHECKS = [
    {
        "check_id": "attention_1",
        "stem": "为确认你正在认真阅读，本题请选择“比较同意”（4）。",
        "expected_value": 4,
    },
    {
        "check_id": "attention_2",
        "stem": "这是一道作答确认题，请选择“比较不同意”（2）。",
        "expected_value": 2,
    },
]

# 语义方向相反的近似题对。反向转换后，两题应大致同向；只作为质量标记，
# 不单独决定答卷无效，避免把真实人格差异误判为随意作答。
CONSISTENCY_PAIRS = [
    (1, False, 21, True),
    (6, True, 36, False),
    (16, False, 31, True),
    (2, True, 17, False),
    (12, True, 42, False),
    (27, True, 32, False),
    (3, False, 8, True),
    (13, False, 23, True),
    (18, True, 38, False),
    (4, False, 9, True),
    (14, False, 34, True),
    (30, False, 41, True),
]


def scored_value(raw: int, reverse: bool) -> int:
    """反向题：6 - 原分。"""
    return (6 - raw) if reverse else raw


def compute_dimension_scores(
    answers: dict[int, int],
    items: list[tuple[int, str, bool]],
) -> dict[str, float]:
    """
    answers: {题号: 原始1-5}
    items: [(题号, 维度, 是否反向), ...]
    返回各维度均分，保留两位小数。
    """
    buckets: dict[str, list[int]] = {"E": [], "A": [], "C": [], "N": [], "O": []}
    for item_no, dimension, reverse in items:
        raw = answers[item_no]
        buckets[dimension].append(scored_value(raw, reverse))

    return {
        dim: round(sum(vals) / len(vals), 2) if vals else 0.0
        for dim, vals in buckets.items()
    }


def build_summary_label(scores: dict[str, float]) -> str:
    """生成类似前端的人格摘要，如「高开放 · 高宜人」。"""
    high = []
    for dim in ("O", "C", "E", "A"):
        if scores.get(dim, 0) >= 4.0:
            high.append(f"高{DIMENSION_NAMES[dim]}")
    if scores.get("N", 0) <= 2.5:
        high.append("稳定")
    elif scores.get("N", 0) >= 4.0:
        high.append("高情绪敏感")
    return " · ".join(high) if high else "均衡型"


def check_quality(
    answers: dict[int, int],
    *,
    duration_seconds: float | None = None,
    attention_answers: dict[str, int] | None = None,
) -> tuple[bool, dict]:
    """
    多指标质量检查。

    单个可疑指标只进入人工复核；同时命中两个独立类别，或两道注意力题
    均答错，才判定未通过。这样能识别明显的随意作答，同时降低误伤。
    返回 (是否通过, 标记详情)
    """
    flags: dict = {"rule_version": QUALITY_RULE_VERSION}
    ordered = [answers[i] for i in range(1, 45)]
    run = 1
    max_run = 1
    for i in range(1, len(ordered)):
        if ordered[i] == ordered[i - 1]:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    unique_count = len(set(ordered))
    response_sd = pstdev(ordered)
    dominant_share = max(ordered.count(value) for value in range(1, 6)) / len(ordered)

    pair_gaps = [
        abs(scored_value(answers[a], reverse_a) - scored_value(answers[b], reverse_b))
        for a, reverse_a, b, reverse_b in CONSISTENCY_PAIRS
    ]
    mean_pair_gap = sum(pair_gaps) / len(pair_gaps)
    large_pair_gaps = sum(gap >= 3 for gap in pair_gaps)

    attention_answers = attention_answers or {}
    attention_failed = [
        check["check_id"]
        for check in ATTENTION_CHECKS
        if attention_answers.get(check["check_id"]) != check["expected_value"]
    ]

    categories: list[str] = []
    response_behavior_reasons: list[str] = []
    if max_run >= 10:
        response_behavior_reasons.append("longstring")
    if dominant_share >= 0.80:
        response_behavior_reasons.append("dominant_option")
    if response_sd < 0.50:
        response_behavior_reasons.append("low_variability")
    consistency_triggered = mean_pair_gap >= 2.5 or large_pair_gaps >= 4
    if consistency_triggered:
        response_behavior_reasons.append("inconsistent_pairs")

    # 连续同答、低变异与正反题不一致可能由同一种作答模式共同造成，
    # 因此合并为一个证据类别，避免对人格问卷中的真实低变异反应重复计数。
    if response_behavior_reasons:
        categories.append("response_behavior")
    if duration_seconds is not None and duration_seconds < 120:
        categories.append("very_fast")
    if attention_failed:
        categories.append("attention_check")

    passed = len(categories) < 2 and len(attention_failed) < len(ATTENTION_CHECKS)

    flags["max_same_streak"] = max_run
    flags["unique_response_count"] = unique_count
    flags["response_sd"] = round(response_sd, 3)
    flags["dominant_option_share"] = round(dominant_share, 3)
    flags["mean_consistency_pair_gap"] = round(mean_pair_gap, 3)
    flags["large_consistency_pair_gaps"] = large_pair_gaps
    flags["duration_seconds"] = (
        round(max(duration_seconds, 0), 1) if duration_seconds is not None else None
    )
    flags["attention_failed"] = attention_failed
    flags["response_behavior_reasons"] = response_behavior_reasons
    flags["triggered_categories"] = categories
    flags["review_recommended"] = bool(categories)
    return passed, flags
