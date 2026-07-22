"""猎鹿博弈：收益矩阵 + 机器人对手。"""

from __future__ import annotations

import random

from app.data.stag_hunt_seed import BOT_COOP_RATE


def calc_payoff(mine: str, theirs: str) -> tuple[int, int]:
    """返回 (我的得分, 对方得分)。"""
    mine = mine.upper()
    theirs = theirs.upper()
    if mine == "A" and theirs == "A":
        return 10, 10
    if mine == "A" and theirs == "B":
        return 0, 6
    if mine == "B" and theirs == "A":
        return 6, 0
    if mine == "B" and theirs == "B":
        return 6, 6
    raise ValueError(f"非法选择: {mine}/{theirs}")


def bot_choice(bot_seed: int, round_no: int, coop_rate: float = BOT_COOP_RATE) -> str:
    """可复现的机器人选择：约 coop_rate 概率选 A。"""
    rng = random.Random(bot_seed + round_no * 10007)
    return "A" if rng.random() < coop_rate else "B"


def demo_bot_choice(rng: random.Random, bias_rate: float = 0.6) -> str:
    """演示用人机：每轮随机偏向一侧（bias_rate），长期 A/B 仍约各 50%。"""
    preferred = "A" if rng.random() < 0.5 else "B"
    if rng.random() < bias_rate:
        return preferred
    return "B" if preferred == "A" else "A"
