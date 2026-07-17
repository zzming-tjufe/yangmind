DEFAULT_PAGES = [
    {
        "page_key": "bfi",
        "title": "BFI-44 人格问卷",
        "subtitle": "完成问卷后即可解锁全部博弈实验",
        "status": "published",
        "audience": "participant",
        "sort_order": 1,
    },
    {
        "page_key": "games",
        "title": "博弈 PK",
        "subtitle": "选择实验，观察你的合作与决策模式",
        "status": "published",
        "audience": "participant",
        "sort_order": 2,
    },
    {
        "page_key": "rank",
        "title": "排行榜",
        "subtitle": "看看本周谁最擅长建立合作",
        "status": "published",
        "audience": "participant",
        "sort_order": 3,
    },
]

DEFAULT_CONTENT_BLOCKS = [
    {
        "block_key": "bfi.intro",
        "title": "认识大五人格模型",
        "body": (
            "在开始作答前，请先阅读以下简要介绍，了解问卷所测量的五项人格维度。\n\n"
            "人格特质没有绝对的好坏之分。本问卷结果仅用于本次研究中的行为分析，不作为临床诊断依据。"
        ),
    },
    {
        "block_key": "bfi.survey_hero",
        "title": "先认识自己的决策底色",
        "body": "BFI-44 用 44 个简短陈述了解你的五项人格维度。请根据真实、稳定的自己作答。",
    },
    {
        "block_key": "games.lobby",
        "title": "选择一种博弈",
        "body": "观察在不同收益结构下，你如何建立信任、权衡风险。",
    },
    {
        "block_key": "rank.hero",
        "title": "合作不只是策略，也是成绩",
        "body": "排行榜综合累计得分、有效场次与人格摘要（来自真实后端数据）。",
    },
    {
        "block_key": "announcement.banner",
        "title": "平台公告",
        "body": "",
    },
]
