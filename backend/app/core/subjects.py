# backend/app/core/subjects.py
"""学科注册表：每个学科用哪个页面解析器、支持哪些题型。

本期只有数学实现；语文/英语仅占位，上传时由路由返回 400。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SubjectSpec:
    id: str
    label: str
    parser_id: str                  # 该学科用哪个页面解析器
    work_mode_ids: tuple[str, ...]  # 该学科可用的题型（来自 work_modes 注册表）
    implemented: bool = True


SUBJECTS: dict[str, SubjectSpec] = {
    "数学": SubjectSpec(
        "数学", "数学", "math_page",
        ("oral", "vertical", "step", "equation", "pattern", "compare",
         "unit_compare", "fill_vertical", "letter_pattern", "geometry",
         "app", "choice", "judge", "other"),
    ),
    # 以下本期不实现，仅占位表明扩展点。work_mode_ids 里的 id 尚未注册到
    # work_modes（等实现语文/英语时一起加），因此「注册表完整性」测试只校验数学。
    "语文": SubjectSpec(
        "语文", "语文", "text_page",
        ("pinyin", "dictation", "fill_blank", "reading", "comprehension", "other"),
        implemented=False,
    ),
    "英语": SubjectSpec(
        "英语", "英语", "text_page",
        ("word_spelling", "listening", "cloze", "reading", "choice", "other"),
        implemented=False,
    ),
}


def spec_of(subject: str | None) -> SubjectSpec:
    """未知/空学科回落数学（练习册默认数学）。"""
    return SUBJECTS.get((subject or "").strip(), SUBJECTS["数学"])


def is_implemented(subject: str | None) -> bool:
    return spec_of(subject).implemented