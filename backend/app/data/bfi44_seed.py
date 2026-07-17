"""BFI-44 题干与计分元数据（与前端 app.js 题序一致）。"""

# 标准 BFI-44：维度 + 是否反向计分（反向题先 6-分 再参与均分）
# 来源：John & Srivastava Big Five Inventory 常用计分表
BFI44_ITEMS: list[dict] = [
    {"item_no": 1, "stem": "是健谈的", "dimension": "E", "reverse_scored": False},
    {"item_no": 2, "stem": "容易挑剔他人", "dimension": "A", "reverse_scored": True},
    {"item_no": 3, "stem": "做事彻底、可靠", "dimension": "C", "reverse_scored": False},
    {"item_no": 4, "stem": "容易情绪低落", "dimension": "N", "reverse_scored": False},
    {"item_no": 5, "stem": "富有创造性", "dimension": "O", "reverse_scored": False},
    {"item_no": 6, "stem": "比较含蓄、安静", "dimension": "E", "reverse_scored": True},
    {"item_no": 7, "stem": "乐于助人且无私", "dimension": "A", "reverse_scored": False},
    {"item_no": 8, "stem": "有时会粗心大意", "dimension": "C", "reverse_scored": True},
    {"item_no": 9, "stem": "能很好地应对压力", "dimension": "N", "reverse_scored": True},
    {"item_no": 10, "stem": "对许多事物好奇", "dimension": "O", "reverse_scored": False},
    {"item_no": 11, "stem": "精力充沛", "dimension": "E", "reverse_scored": False},
    {"item_no": 12, "stem": "有时会与他人争执", "dimension": "A", "reverse_scored": True},
    {"item_no": 13, "stem": "值得信赖地完成工作", "dimension": "C", "reverse_scored": False},
    {"item_no": 14, "stem": "容易紧张", "dimension": "N", "reverse_scored": False},
    {"item_no": 15, "stem": "善于深入思考", "dimension": "O", "reverse_scored": False},
    {"item_no": 16, "stem": "能激发他人热情", "dimension": "E", "reverse_scored": False},
    {"item_no": 17, "stem": "天性宽容", "dimension": "A", "reverse_scored": False},
    {"item_no": 18, "stem": "做事容易缺乏条理", "dimension": "C", "reverse_scored": True},
    {"item_no": 19, "stem": "经常忧虑", "dimension": "N", "reverse_scored": False},
    {"item_no": 20, "stem": "想象力活跃", "dimension": "O", "reverse_scored": False},
    {"item_no": 21, "stem": "比较安静", "dimension": "E", "reverse_scored": True},
    {"item_no": 22, "stem": "通常信任他人", "dimension": "A", "reverse_scored": False},
    {"item_no": 23, "stem": "有时会有点懒惰", "dimension": "C", "reverse_scored": True},
    {"item_no": 24, "stem": "情绪稳定", "dimension": "N", "reverse_scored": True},
    {"item_no": 25, "stem": "有创造力", "dimension": "O", "reverse_scored": False},
    {"item_no": 26, "stem": "性格坚定、自信", "dimension": "E", "reverse_scored": False},
    {"item_no": 27, "stem": "有时冷淡", "dimension": "A", "reverse_scored": True},
    {"item_no": 28, "stem": "能坚持到任务完成", "dimension": "C", "reverse_scored": False},
    {"item_no": 29, "stem": "情绪多变", "dimension": "N", "reverse_scored": False},
    {"item_no": 30, "stem": "重视艺术与审美", "dimension": "O", "reverse_scored": False},
    {"item_no": 31, "stem": "有时害羞拘谨", "dimension": "E", "reverse_scored": True},
    {"item_no": 32, "stem": "体贴、友善", "dimension": "A", "reverse_scored": False},
    {"item_no": 33, "stem": "做事有效率", "dimension": "C", "reverse_scored": False},
    {"item_no": 34, "stem": "在紧张情境中冷静", "dimension": "N", "reverse_scored": True},
    {"item_no": 35, "stem": "偏好常规", "dimension": "O", "reverse_scored": True},
    {"item_no": 36, "stem": "外向善于社交", "dimension": "E", "reverse_scored": False},
    {"item_no": 37, "stem": "有时态度粗鲁", "dimension": "A", "reverse_scored": True},
    {"item_no": 38, "stem": "会制定计划并执行", "dimension": "C", "reverse_scored": False},
    {"item_no": 39, "stem": "容易紧张不安", "dimension": "N", "reverse_scored": False},
    {"item_no": 40, "stem": "喜欢探索复杂观点", "dimension": "O", "reverse_scored": False},
    {"item_no": 41, "stem": "对艺术兴趣不大", "dimension": "O", "reverse_scored": True},
    {"item_no": 42, "stem": "喜欢与他人合作", "dimension": "A", "reverse_scored": False},
    {"item_no": 43, "stem": "容易分心", "dimension": "C", "reverse_scored": True},
    {"item_no": 44, "stem": "对艺术很有鉴赏力", "dimension": "O", "reverse_scored": False},
]

INSTRUMENT_CODE = "BFI-44"
INSTRUMENT_VERSION = "1.0"
INSTRUMENT_TITLE = "BFI-44 人格问卷"
