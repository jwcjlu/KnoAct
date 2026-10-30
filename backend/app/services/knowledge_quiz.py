"""知识点主动复习：知识点→简答题出题 + 混合判分（规则优先，AI 兜底）。"""
import json

from sqlalchemy.orm import Session

from .ai import get_provider

# 规则判分关键词命中阈值（与 mastery.grade_answer 的 open 题型一致）
_HIT_THRESHOLD = 0.6


def generate_knowledge_questions(db: Session, points: list[dict], subject: str) -> list[dict]:
    """把知识点列表转成简答题，返回 [{id, content, category, question, answer, keywords}]。

    fake provider / 异常回退：question 为空字符串，answer 空，keywords 空。
    """
    provider = get_provider(db)
    if provider.name == "fake":
        return [{"id": p.get("id"), "content": p.get("content", ""),
                 "category": p.get("category", ""), "question": "",
                 "answer": "", "keywords": []} for p in points]
    prompt = (
        "针对下面每个知识点出一道简答题，让孩子凭记忆作答，检验是否真正掌握。\n"
        "知识点列表（JSON，含 id / content / category）：\n"
        f"{json.dumps(points, ensure_ascii=False)}\n"
        '只返回 JSON：{"questions":[{"id":知识点id,"question":"问题","answer":"标准答案",'
        '"keywords":["判分关键词1","关键词2"]}]}。keywords 是判断孩子答对所需的关键词，3~5 个。'
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是出题老师。", json_mode=True)
        data = json.loads(raw)
        qmap = {q.get("id"): q for q in (data.get("questions") or [])}
    except Exception:
        qmap = {}
    out = []
    for p in points:
        q = qmap.get(p.get("id"), {})
        out.append({
            "id": p.get("id"), "content": p.get("content", ""),
            "category": p.get("category", ""),
            "question": (q.get("question") or "").strip(),
            "answer": (q.get("answer") or "").strip(),
            "keywords": [k.strip() for k in (q.get("keywords") or []) if k.strip()],
        })
    return out


def _hit_rate(user_answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    matched = sum(1 for kw in keywords if kw in user_answer)
    return matched / len(keywords)


def _ai_grade(db: Session, user_answer: str, answer: str) -> bool:
    provider = get_provider(db)
    if provider.name == "fake":
        return False
    try:
        raw = provider.generate(
            prompt=f"孩子的答案是「{user_answer}」，标准答案是「{answer}」。孩子答对了吗？只返回 true 或 false。",
            system="你是判分老师。", json_mode=False)
        return raw.strip().lower().startswith("true")
    except Exception:
        return False


def grade_knowledge_answer(user_answer: str, keywords: list[str], answer: str,
                           db: Session | None = None) -> tuple[bool, bool]:
    """混合判分。返回 (is_correct, used_ai)。

    - 关键词命中 >= 阈值 → 判对（规则）
    - 空答案或关键词全不命中 → 判错（规则）
    - 中间态（0 < 命中 < 阈值）→ AI 兜底（db 提供时）
    """
    ua = (user_answer or "").strip()
    if not ua:
        return False, False
    rate = _hit_rate(ua, keywords)
    if rate >= _HIT_THRESHOLD:
        return True, False
    if rate == 0.0:
        return False, False
    if db is not None:
        return _ai_grade(db, ua, answer), True
    return False, False
