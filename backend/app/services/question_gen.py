"""阅读理解题生成：基于课文文本让 AI 出题，失败时回退内置兜底题。

入库（seed / PDF 拆课）与后台「重新生成」共用此服务，保证逻辑一致。
"""
import json

from sqlalchemy.orm import Session

from .ai import get_provider

FALLBACK_QUESTIONS = [
    # TODO: 兜底题写死为一条通用题，AI 不可用/解析失败时所有课文都返回它，需按课文定制或扩充题库
    {"question": "文中作者表达了什么感情？", "answer": "对故乡的喜爱"},
]


def generate_reading_questions(db: Session, text: str, n: int = 3) -> list[dict]:
    """针对课文出 n 道阅读理解题，返回 [{question, answer}]。

    任何异常（无 API Key、解析失败、provider 不可用）都回退到兜底题，
    绝不抛异常中断调用方（入库流程）。
    """
    if not text or not text.strip():
        return FALLBACK_QUESTIONS
    provider = get_provider(db)
    if provider.name == "fake":
        return FALLBACK_QUESTIONS
    prompt = (
        f"针对下面这篇课文出 {n} 道阅读理解题，题目要基于课文内容、适合小学生作答。\n"
        '只返回 JSON，格式：{"questions":[{"question":"题目","answer":"答案"}]}。\n\n'
        f"课文：\n{text[:800]}"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是语文老师。", json_mode=True)
        data = json.loads(raw)
        qs = data.get("questions") or []
        out = []
        for q in qs:
            question = (q.get("question") or "").strip()
            answer = (q.get("answer") or "").strip()
            if question and answer:
                out.append({"question": question, "answer": answer})
        return out[:n] if out else FALLBACK_QUESTIONS
    except Exception:
        return FALLBACK_QUESTIONS
