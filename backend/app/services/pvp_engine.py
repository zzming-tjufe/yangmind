"""真人同步对局：结算与超时规则。"""

from __future__ import annotations

from app.services.game_engine import calc_payoff

# 超时未选时，矩阵结算按对方视为选 B；未选方得分强制为 0
TIMEOUT_FILL_CHOICE = "B"


def resolve_pvp_payoff(
    choice_a: str | None,
    choice_b: str | None,
    *,
    a_timed_out: bool,
    b_timed_out: bool,
) -> tuple[int, int]:
    """
    返回 (A得分, B得分)。
    - 双方都超时：都是 0
    - 一方超时：超时方 0；另一方按「对方=B」用矩阵结算
    - 双方都选：正常矩阵
    """
    if a_timed_out and b_timed_out:
        return 0, 0

    eff_a = (choice_a or TIMEOUT_FILL_CHOICE).upper()
    eff_b = (choice_b or TIMEOUT_FILL_CHOICE).upper()
    points_a, points_b = calc_payoff(eff_a, eff_b)

    if a_timed_out:
        points_a = 0
    if b_timed_out:
        points_b = 0
    return points_a, points_b
