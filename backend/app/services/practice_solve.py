"""AI 求解：把题面页的算式批量交给 LLM 算出答案。"""
import json
import re

_SOLVE_SYSTEM = (
    "你是小学数学老师，负责算出计算题的标准答案。\n"
    "只输出 JSON，格式：{\"answers\":[{\"index\":0,\"answer\":\"13.4\"}, ...]}\n"
    "answer 只写最终结果数字（保留原题所需的小数位，不要写单位、不要写过程）。"
    "index 与输入编号严格对应。"
)


def _parse_solve(raw: str) -> dict[int, str]:
    """把 LLM 返回的 JSON 解析成 {index: answer}。"""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        m = re.search(r"\{[\s\S]*\}", raw or "")
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
        except (ValueError, TypeError):
            return {}

    items = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {}

    out: dict[int, str] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            idx = int(it.get("index"))
        except (TypeError, ValueError):
            continue
        ans = str(it.get("answer") or "").strip()
        if ans:
            out[idx] = ans
    return out


def solve_math_items(db, items: list[dict], *, batch_size: int = 20) -> dict[int, str]:
    """批量求答案。items 是 parse_lesson_page 的产出，返回 {列表下标: 答案}。

    fake provider 或调用失败时返回已成功的部分（缺的进「待补答案」清单）。
    """
    from .ai import get_provider

    if not items:
        return {}
    provider = get_provider(db)
    if provider.name == "fake":
        return {}

    answers: dict[int, str] = {}
    for start in range(0, len(items), batch_size):
        chunk = items[start:start + batch_size]
        lines = [
            f"{i}. {it.get('question', '')}"
            for i, it in enumerate(chunk)
        ]
        prompt = (
            "算出下面每道题的最终答案，index 从 0 开始按顺序编号。\n"
            + "\n".join(lines)
        )
        try:
            raw = provider.generate(prompt=prompt, system=_SOLVE_SYSTEM,
                                    json_mode=True)
            got = _parse_solve(raw)
        except Exception:
            got = {}
        for local_idx, ans in got.items():
            if 0 <= local_idx < len(chunk):
                answers[start + local_idx] = ans
    return answers
