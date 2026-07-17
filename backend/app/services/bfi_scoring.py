"""BFI-44 计分与简易质量检查。"""

from __future__ import annotations

DIMENSION_NAMES = {
    "E": "外向",
    "A": "宜人",
    "C": "尽责",
    "N": "情绪敏感",
    "O": "开放",
}


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


def check_quality(answers: dict[int, int]) -> tuple[bool, dict]:
    """
    简易质量检查：
    - 是否有连续 10 题以上完全相同
    返回 (是否通过, 标记详情)
    """
    flags: dict = {}
    ordered = [answers[i] for i in range(1, 45)]
    run = 1
    max_run = 1
    for i in range(1, len(ordered)):
        if ordered[i] == ordered[i - 1]:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    if max_run >= 10:
        flags["long_same_streak"] = max_run

    passed = "long_same_streak" not in flags
    flags["max_same_streak"] = max_run
    return passed, flags
