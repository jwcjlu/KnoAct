"""个性化学习作业：AI 现场出题（按学科难度 + 题数），失败回退兜底题。"""
import json

from sqlalchemy.orm import Session

from .ai import get_provider

# 难度档位 → 出题 prompt 约束片段
DIFFICULTY_PROMPT = {
    "简单": "题目要基础、直白，考察课文中最明显的信息。",
    "中等": "题目要适中，考察对课文内容的理解与简单推断。",
    "困难": "题目要有一定深度，考察对课文主旨、细节与隐含含义的把握。",
}

FALLBACK_ASSIGNMENT = [
    {"question": "这篇课文主要讲了什么？", "answer": "课文的主要内容", "knowledge_point_id": None},
    {"question": "你从课文里学到了什么？", "answer": "结合课文谈收获", "knowledge_point_id": None},
]


def generate_assignment(db: Session, text: str, subject: str = "语文",
                        difficulty: str = "中等", n: int = 4,
                        knowledge_points: list[dict] | None = None,
                        previous_questions: list[str] | None = None,
                        wrong_questions: list[str] | None = None) -> list[dict]:
    """针对课文现场出 n 道作业题，返回 [{question, answer, knowledge_point_id}]。

    传入 knowledge_points（[{id, category, content}]）时，让 AI 每题关联一个知识点
    id（不匹配则 null），供判分后落 KnowledgeMastery 驱动遗忘曲线。
    previous_questions 为本课已出过的题（新题不得重复），wrong_questions 为上一组答错的题
    （新题围绕同类内容换个问法再考）。任何异常回退兜底题。
    """
    if not text or not text.strip():
        return FALLBACK_ASSIGNMENT
    provider = get_provider(db)
    if provider.name == "fake":
        return FALLBACK_ASSIGNMENT
    diff_hint = DIFFICULTY_PROMPT.get(difficulty, DIFFICULTY_PROMPT["中等"])
    prompt = (
        f"针对下面这篇「{subject}」课文出 {n} 道作业题，适合小学生作答。\n"
        f"{diff_hint}\n"
    )
    if knowledge_points:
        prompt += (
            "\n本课的知识点列表（JSON，含 id / category / content）：\n"
            f"{json.dumps(knowledge_points, ensure_ascii=False)}\n"
            '每道题额外返回 "knowledge_point_id"：从上面列表里选最相关的一个知识点 id；若都不匹配则填 null。\n'
        )
    if previous_questions:
        prompt += "\n下面这些题已经出过，新题不要与它们重复：\n" + "\n".join(f"- {q}" for q in previous_questions[-20:]) + "\n"
    if wrong_questions:
        prompt += "\n孩子上一组答错了下面这些题，新题要围绕同样的内容换个角度或问法再考：\n" + "\n".join(f"- {q}" for q in wrong_questions) + "\n"
    prompt += '只返回 JSON，格式：{"questions":[{"question":"题目","answer":"答案","knowledge_point_id":1或null}]}。\n\n' + f"课文：\n{text[:1200]}"
    try:
        raw = provider.generate(prompt=prompt, system="你是出题老师。", json_mode=True)
        data = json.loads(raw)
        qs = data.get("questions") or []
        out = []
        for q in qs:
            question = (q.get("question") or "").strip()
            answer = (q.get("answer") or "").strip()
            kpid = q.get("knowledge_point_id")
            if not isinstance(kpid, int):
                kpid = None
            if question and answer:
                out.append({"question": question, "answer": answer, "knowledge_point_id": kpid})
        return out[:n] if out else FALLBACK_ASSIGNMENT
    except Exception:
        return FALLBACK_ASSIGNMENT


def _normalize(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isalnum()).lower()


_NEGATIONS = "不没非未无"


def _rule_grade(student: str, reference: str) -> bool:
    """AI 不可用时的兜底判分（去掉标点空白后比较）。

    相等判对；学生答案包含参考答案且前面不是否定字（避免「不相等」命中「相等」）判对；
    学生答案是参考答案的片段且长度过半（如漏写单位）判对。
    """
    a, b = _normalize(student), _normalize(reference)
    if not a or not b:
        return False
    if a == b:
        return True
    idx = a.find(b)
    if idx >= 0:
        return idx == 0 or a[idx - 1] not in _NEGATIONS
    return a in b and len(a) * 2 >= len(b)


def grade_assignment(db: Session, items: list[dict]) -> list[dict]:
    """逐题判分，返回与 items 等长的 [{is_correct, feedback}]。

    items: [{question, answer(参考答案), student_answer}]。开放题按意思判，不要求与参考答案字面一致；
    未作答一律判错。AI 不可用或返回异常时回退 _rule_grade。
    """
    results = [{"is_correct": False, "feedback": ""} for _ in items]
    pending = [i for i, it in enumerate(items) if (it.get("student_answer") or "").strip()]
    if not pending:
        return results

    def fallback():
        for i in pending:
            results[i]["is_correct"] = _rule_grade(items[i].get("student_answer", ""), items[i].get("answer", ""))
        return results

    provider = get_provider(db)
    if provider.name == "fake":
        return fallback()
    payload = [{"index": i, "question": items[i].get("question", ""), "reference": items[i].get("answer", ""),
                "student_answer": items[i].get("student_answer", "")} for i in pending]
    prompt = (
        "下面是小学生的作业答案，请逐题判断是否答对。\n"
        "判分要求：按意思判断，只要抓住了参考答案的要点就算对，不要求字面一致，也不苛求表述完整；"
        "答非所问、意思错误或关键要点缺失算错。\n"
        "每题给一句不超过 40 字、适合小学生的讲解：答对时肯定要点，答错时指出错在哪里。\n"
        '只返回 JSON，格式：{"results":[{"index":题号,"is_correct":true或false,"feedback":"讲解"}]}。\n\n'
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是耐心的小学老师，负责批改作业。", json_mode=True)
        data = json.loads(raw)
        graded = {r.get("index"): r for r in (data.get("results") or []) if isinstance(r, dict)}
        if not all(i in graded for i in pending):
            return fallback()
        for i in pending:
            r = graded[i]
            results[i]["is_correct"] = r.get("is_correct") is True
            results[i]["feedback"] = str(r.get("feedback") or "").strip()
        return results
    except Exception:
        return fallback()
