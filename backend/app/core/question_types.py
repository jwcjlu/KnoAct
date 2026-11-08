"""题型 taxonomy：category（判分方式）→ qtype（展示/录入）。"""
CATEGORIES = ("choice", "blank", "match", "subjective")

CATEGORY_OF_QTYPE: dict[str, str] = {
    "single_choice": "choice",
    "multi_choice": "choice",
    "true_false": "choice",
    "fill_blank": "blank",
    "cloze": "blank",
    "calculation": "blank",
    "matching": "match",
    "short_answer": "subjective",
    "essay": "subjective",
    "application": "subjective",
    "oral": "subjective",
}

QTYPE_LABELS: dict[str, str] = {
    "single_choice": "单选题",
    "multi_choice": "多选题",
    "true_false": "判断题",
    "fill_blank": "填空题",
    "cloze": "完形填空",
    "calculation": "计算题",
    "matching": "连线题",
    "short_answer": "简答题",
    "essay": "作文",
    "application": "应用题",
    "oral": "口语题",
}

QTYPES = tuple(CATEGORY_OF_QTYPE.keys())

# 旧 qtype 粗粒度值 → taxonomy 最近项
LEGACY_QTYPE_MAP: dict[str, str] = {
    "reading": "short_answer",
    "listening": "single_choice",
    "knowledge": "short_answer",
    "math": "application",
}
