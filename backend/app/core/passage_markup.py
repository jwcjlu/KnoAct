"""阅读材料轻量标记：挖空计数。渲染在前端，这里只做对齐校验。"""

BLANK = "____"
FILL_BLANK_QTYPES = frozenset({"fill_blank", "cloze"})


def count_blanks(content: str) -> int:
    return (content or "").count(BLANK)


def blanks_aligned(content: str, fill_blank_count: int) -> bool:
    """无填空子题时不强制；有填空子题时 ____ 个数必须相等。"""
    if fill_blank_count <= 0:
        return True
    return count_blanks(content) == fill_blank_count
