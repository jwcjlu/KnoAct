# backend/app/services/math_grade.py
"""所有数学入口共用的判分门面。

**唯一一份**按 `answer_kind` 分派的实现。`practice_grade.grade_practice_item`
与未来的 `language_grade` 都只做「取字段 → 转交这里」的薄包装，不重复分派逻辑。

返回统一 dict：`{is_correct, ai_status, final_answer, steps_plausible, reason}`
- `is_correct` 为 `None` 表示「无法判定」（缺答案/待人工/AI 未完成），不是「判错」
"""
from .math_gen import grade_math_answer, grade_math_work_photo

# 全角 → 半角（比较符号）
_SYMBOL_MAP = str.maketrans({
    "＞": ">", "＜": "<", "＝": "=",
    "≥": ">=", "≤": "<=",
})


def _result(is_correct, *, ai_status="ok", final_answer="",
            steps_plausible=False, reason="") -> dict:
    return {
        "is_correct": is_correct,
        "ai_status": ai_status,
        "final_answer": final_answer,
        "steps_plausible": steps_plausible,
        "reason": reason,
    }


def _pending(reason: str) -> dict:
    return _result(None, ai_status="pending", reason=reason)


def _norm_symbol(s: str) -> str:
    return (s or "").strip().translate(_SYMBOL_MAP).replace(" ", "")


def _blanks_of(answer_json: dict | None) -> list[str]:
    if not isinstance(answer_json, dict):
        return []
    raw = answer_json.get("blanks")
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw]


def grade_by_answer_kind(
    db,
    *,
    answer_kind: str,
    answer: str,
    answer_json: dict | None = None,
    student_answer: str = "",
    blanks: list | None = None,
    photo_bytes: bytes | None = None,
    question: str = "",
) -> dict:
    """按 answer_kind 分派。绝不抛异常（未知 kind 回落 text）。"""
    kind = (answer_kind or "").strip()
    expected = (answer or "").strip()

    if kind == "number":
        if not expected:
            return _pending("缺少标准答案")
        ok = grade_math_answer(student_answer, expected)
        return _result(ok, final_answer=expected)

    if kind == "numeric_list":
        expected_blanks = _blanks_of(answer_json)
        if not expected_blanks:
            return _pending("缺少分空答案")
        got = [str(x).strip() for x in (blanks or [])]
        if len(got) != len(expected_blanks):
            return _result(False, final_answer=expected)
        ok = all(grade_math_answer(g, e) for g, e in zip(got, expected_blanks))
        return _result(ok, final_answer=expected)

    if kind == "symbol":
        if not expected:
            return _pending("缺少标准答案")
        ok = _norm_symbol(student_answer) == _norm_symbol(expected)
        return _result(ok, final_answer=expected)

    if kind == "choice":
        # answer_json 可能来自 DB，不保证是 dict（可能 None / 字符串 / 列表）
        idx = answer_json.get("correct_index") if isinstance(answer_json, dict) else None
        if idx is None:
            return _pending("缺少正确选项")
        try:
            ok = int(str(student_answer).strip()) == int(idx)
        except (TypeError, ValueError):
            ok = False
        return _result(ok, final_answer=expected or str(idx))

    if kind == "photo":
        if not photo_bytes:
            return _pending("未上传作答照片")
        if not expected:
            return _pending("缺少标准答案")
        r = grade_math_work_photo(db, photo_bytes, question or "", expected)
        status = r.get("ai_status") or "pending"
        # pending_review / failed 都不算判错
        ok = bool(r.get("ai_correct")) if status == "ok" else None
        return _result(
            ok,
            ai_status=status,
            final_answer=r.get("final_answer") or "",
            steps_plausible=bool(r.get("steps_plausible")),
            reason=r.get("reason") or "",
        )

    # text / 未知：交给调用方走既有的主观题判分
    return _pending("需主观判分")
