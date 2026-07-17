"""猎鹿博弈场景文案（与前端 app.js 一致）。"""

STAG_HUNT_CODE = "stag_hunt"
STAG_HUNT_TITLE = "猎鹿博弈"
ROUNDS_PER_SCENE = 10
BOT_COOP_RATE = 0.64  # 与前端 Math.random() < 0.64 一致

STAG_SCENES: list[dict] = [
    {
        "scene_key": "task",
        "no": "01",
        "title": "双人小组任务",
        "short_desc": "你和另一名同学连续进行 10 轮项目决策，每轮同时选择任务投入方式。",
        "option_a": "认真准备共同展示",
        "option_b": "只完成最低限度任务",
        "option_a_text": "只有双方都认真准备，小组展示效果才会很好，双方获得最高收益。",
        "option_b_text": "收益不如共同认真准备高，但风险较小，能获得稳定收益。",
        "required": True,
        "sort_order": 1,
    },
    {
        "scene_key": "travel",
        "no": "02",
        "title": "出行安排",
        "short_desc": "你和另一名同学准备去同一地点参加活动，连续进行 10 轮出行安排。",
        "option_a": "一起拼车",
        "option_b": "各自坐公交",
        "option_a_text": "只有双方都选择拼车才能成功，节省时间并获得最高收益。",
        "option_b_text": "虽然不如成功拼车高效，但风险较小，能够稳定到达目的地。",
        "required": True,
        "sort_order": 2,
    },
]
