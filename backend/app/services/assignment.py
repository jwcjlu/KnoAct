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
                        knowledge_points: list[dict] | None = None) -> list[dict]:
    """针对课文现场出 n 道作业题，返回 [{question, answer, knowledge_point_id}]。

    传入 knowledge_points（[{id, category, content}]）时，让 AI 每题关联一个知识点
    id（不匹配则 null），供判分后落 KnowledgeMastery 驱动遗忘曲线。任何异常回退兜底题。
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
