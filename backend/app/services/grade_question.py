"""多题型判分：客观题精确判，主观题走 AI（未配置回落 pending）。"""
import json
import re
import unicodedata

_SPACING = re.compile(r"[\s\-·、，。,.!！?？:：;；'\"“”‘’()（）\[\]【】]+")


def normalize_answer(value: str) -> str:
    """去空白/标点/大小写/全半角，供填空/计算容错比较。

    NFKC 把全角字母/数字（ＡＢＣ１２３）折成半角，避免孩子或 OCR 输入的全角
    答案被判错。
    """
    return _SPACING.sub("", unicodedata.normalize("NFKC", (value or "").casefold()))


def grade_question(qtype_category: str, answer_json: dict, student_answer: dict) -> dict:
    """返回 {is_correct, correct_answer_text, detail}。

    student_answer 形状按题型：
      choice:  {"selected_index": int | list[int]}
      blank:   {"blanks": [str]}
      match:   {"pairs": [[str,str],...]}
      subjective: {"text": str}
    """
    if qtype_category == "choice":
        ci = answer_json.get("correct_index")
        sel = student_answer.get("selected_index")
        if isinstance(ci, list):
            ok = isinstance(sel, list) and sorted(map(int, sel)) == sorted(map(int, ci))
        else:
            ok = isinstance(sel, int) and not isinstance(sel, bool) and sel == ci
        return {"is_correct": ok, "correct_answer_text": json.dumps(ci, ensure_ascii=False), "detail": "choice"}

    if qtype_category == "blank":
        expected = answer_json.get("blanks") or []
        got = student_answer.get("blanks") or []
        ok = len(expected) == len(got) and all(
            normalize_answer(e) == normalize_answer(g) for e, g in zip(expected, got)
        )
        return {"is_correct": ok, "correct_answer_text": "；".join(expected), "detail": "blank"}

    if qtype_category == "match":
        expected = sorted(tuple(p) for p in (answer_json.get("pairs") or []))
        got = sorted(tuple(p) for p in (student_answer.get("pairs") or []))
        ok = expected == got
        return {"is_correct": ok, "correct_answer_text": json.dumps(answer_json.get("pairs"), ensure_ascii=False), "detail": "match"}

    # subjective：先返回 pending（AI 判分在 Task 4 由 grade_subjective_with_ai 完成）
    return grade_subjective(answer_json, student_answer)


def grade_subjective(answer_json: dict, student_answer: dict) -> dict:
    """主观题 AI 判分；未配置/fake 回落 pending（待家长批改）。"""
    sample = (answer_json.get("sample") or "").strip()
    text = (student_answer.get("text") or "").strip()
    if not text:
        return {"is_correct": False, "correct_answer_text": sample, "detail": "empty"}
    return {"is_correct": None, "correct_answer_text": sample, "detail": "pending"}


def grade_subjective_with_ai(db, answer_json: dict, student_answer: dict) -> dict:
    """主观题 AI 判分。返回 {is_correct: bool|None, correct_answer_text, detail}。

    AI 未配置 / fake / 返回无法解析 → is_correct=None, detail="pending"（待家长批改）。
    """
    from .ai import get_provider

    rubric = (answer_json.get("rubric") or "").strip()
    sample = (answer_json.get("sample") or "").strip()
    text = (student_answer.get("text") or "").strip()
    if not text:
        return {"is_correct": False, "correct_answer_text": sample, "detail": "empty"}

    provider = get_provider(db)
    if provider.name == "fake":
        return {"is_correct": None, "correct_answer_text": sample, "detail": "pending"}

    prompt = (
        f"你是一位小学老师，正在批改一道主观题。\n"
        f"评分要点（rubric）：{rubric or '未提供'}\n"
        f"参考答案：{sample or '未提供'}\n"
        f"学生作答：{text}\n"
        '只返回 JSON：{"is_correct": true 或 false, "reason": "简短评语"}'
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是小学老师，公正批改。", json_mode=True)
        data = json.loads(raw)
        return {
            "is_correct": bool(data.get("is_correct", False)),
            "correct_answer_text": sample,
            "detail": data.get("reason", ""),
        }
    except Exception:
        return {"is_correct": None, "correct_answer_text": sample, "detail": "pending"}
