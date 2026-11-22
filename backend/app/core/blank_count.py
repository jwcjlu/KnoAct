"""判空数：给前端决定渲染几个输入框。"""
import json


def blank_count_of(q) -> int:
    """该题要填几个空。多空题看 answer_json.blanks，其余算 1。

    不能按 answer 里的逗号数推断：单个答案本身含逗号（如 `1,234`）时会多算空，
    而判分严格要求空数一致，多一个空就是永久判错。
    """
    try:
        data = json.loads(getattr(q, "answer_json", "") or "{}")
    except (ValueError, TypeError):
        return 1
    if not isinstance(data, dict):
        return 1
    blanks = data.get("blanks")
    if isinstance(blanks, list) and blanks:
        return len(blanks)
    return 1
