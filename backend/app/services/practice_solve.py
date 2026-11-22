# backend/app/services/practice_solve.py
"""AI 求解：把题面批量交给 LLM 算出答案。

返回结构 `{列表下标: {"kind", "answer", "blanks"}}`：
- `number`       → {"kind": "number", "answer": "13.4"}
- `numeric_list` → {"kind": "numeric_list", "blanks": ["1.2","1.44"], "answer": "1.2, 1.44"}
- `symbol`       → {"kind": "symbol", "answer": ">"}
"""
import json
import re

_SOLVE_SYSTEM = (
    "你是小学数学老师，负责算出每道题的标准答案。\n"
    "只输出 JSON，格式：\n"
    '{"answers":[{"index":0,"kind":"number","answer":"13.4"},'
    '{"index":1,"kind":"numeric_list","blanks":["1.2","1.44"]},'
    '{"index":2,"kind":"symbol","answer":">"}]}\n'
    "kind 只能是 number / numeric_list / symbol。\n"
    "- 单答案填 kind=number, answer=最终结果（保留原题小数位，不写单位、不写过程）。\n"
    "- 一题多空填 kind=numeric_list，blanks 按空位顺序排列，不要填 answer。\n"
    "- 比较大小填 kind=symbol，answer 是 > < = 之一。\n"
    "index 与输入编号严格对应。示例行不要计算。"
)

_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _provider_ready(db) -> bool:
    """fake provider 或未配置时不求解（缺答案进「待补答案」）。"""
    try:
        from .ai import get_provider

        return get_provider(db).name != "fake"
    except Exception:
        return False


def _parse_solve(raw: str) -> dict[int, dict]:
    """把 LLM 返回的 JSON 解析成 {index: {kind, answer, blanks}}。"""
    try:
        data = json.loads(raw or "")
    except (ValueError, TypeError):
        m = _JSON_RE.search(raw or "")
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
        except (ValueError, TypeError):
            return {}

    items = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {}

    out: dict[int, dict] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            idx = int(it.get("index"))
        except (TypeError, ValueError):
            continue
        kind = str(it.get("kind") or "number").strip()
        if kind == "numeric_list":
            raw_blanks = it.get("blanks")
            blanks = ([str(x).strip() for x in raw_blanks]
                      if isinstance(raw_blanks, list) else [])
            blanks = [b for b in blanks if b]
            if not blanks:
                continue
            out[idx] = {"kind": "numeric_list", "blanks": blanks,
                        "answer": ", ".join(blanks)}
            continue
        ans = str(it.get("answer") or "").strip()
        if not ans:
            continue
        out[idx] = {"kind": "symbol" if kind == "symbol" else "number",
                    "answer": ans}
    return out


def _call_solver(db, chunk: list[dict]) -> dict[int, dict]:
    from .ai import get_provider

    provider = get_provider(db)
    lines = [f"{i}. {it.get('question', '')}" for i, it in enumerate(chunk)]
    prompt = (
        "算出下面每道题的最终答案，index 从 0 开始按顺序编号。\n"
        + "\n".join(lines)
    )
    raw = provider.generate(prompt=prompt, system=_SOLVE_SYSTEM, json_mode=True)
    return _parse_solve(raw)


def solve_math_items(
    db,
    items: list[dict],
    *,
    batch_size: int = 20,
    on_progress=None,
) -> dict[int, dict]:
    """批量求答案。返回 {列表下标: {kind, answer, blanks}}。

    未配置 provider / 调用失败时返回已成功的部分（缺的进「待补答案」）。"""
    if not items:
        return {}
    if not _provider_ready(db):
        return {}

    answers: dict[int, dict] = {}
    total = len(items)
    for start in range(0, total, batch_size):
        chunk = items[start:start + batch_size]
        try:
            got = _call_solver(db, chunk)
        except Exception:
            got = {}
        for local_idx, payload in got.items():
            if 0 <= local_idx < len(chunk):
                answers[start + local_idx] = payload
        if on_progress is not None:
            try:
                on_progress(len(answers), total)
            except Exception:
                pass
    return answers
