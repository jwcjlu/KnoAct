"""边读边问：测验（quiz）与主动提问（ask questions）。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Quiz, Text, KnowledgePoint
from ..services.quiz import (
    QuizGenerationError, generate_quiz, grade_answers, strip_key,
)

router = APIRouter(prefix="/api", tags=["read-and-ask"])


class QuizGenerateReq(BaseModel):
    lesson_id: int
    user_id: int = 0


class QuizSubmitReq(BaseModel):
    quiz_id: int
    answers: list[dict]


class AskQuestionsReq(BaseModel):
    lesson_id: int
    context: str = ""


class AskReplyReq(BaseModel):
    lesson_id: int
    context: str = ""
    replies: dict = {}


def _lesson_text(db: Session, lesson_id: int) -> str:
    t = db.query(Text).filter_by(lesson_id=lesson_id).first()
    return t.content if t else ""


@router.post("/quiz/generate")
def quiz_generate(req: QuizGenerateReq, db: Session = Depends(get_db)):
    text = _lesson_text(db, req.lesson_id)
    if not text:
        raise HTTPException(status_code=400, detail="该课文暂无内容，无法出题")
    try:
        kps = [{"id": k.id, "category": k.category, "content": k.content}
               for k in db.query(KnowledgePoint).filter_by(lesson_id=req.lesson_id).all()]
        questions = generate_quiz(db, text, n=3, knowledge_points=kps)
    except QuizGenerationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    quiz = Quiz(lesson_id=req.lesson_id, user_id=req.user_id,
                questions=json.dumps(questions, ensure_ascii=False))
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return {"quiz_id": quiz.id, "questions": strip_key(questions)}


@router.post("/quiz/submit")
def quiz_submit(req: QuizSubmitReq, db: Session = Depends(get_db)):
    quiz = db.get(Quiz, req.quiz_id)
    if not quiz:
        raise HTTPException(status_code=409, detail="测验已过期")
    questions = json.loads(quiz.questions)
    valid_ids = {q["id"] for q in questions}
    for a in req.answers:
        if a.get("question_id") not in valid_ids:
            raise HTTPException(status_code=409, detail="测验已过期")
        if not isinstance(a.get("selected_index"), int):
            raise HTTPException(status_code=422, detail="选项无效")
    results = grade_answers(questions, req.answers)
    if quiz.user_id:
        from ..services.mastery import record_attempt as record_mastery
        for q, r in zip(questions, results):
            kpid = q.get("knowledge_point_id")
            if kpid is not None:
                record_mastery(db, quiz.user_id, "knowledge", kpid, r["is_correct"])
    score = sum(1 for r in results if r["is_correct"])
    quiz.score = score
    db.commit()
    return {"answers": results, "score": score, "total": len(questions)}


@router.post("/ask/questions")
def ask_questions(req: AskQuestionsReq, db: Session = Depends(get_db)):
    from ..services.ai import get_provider
    provider = get_provider(db)
    if provider.name == "fake":
        raise HTTPException(status_code=503, detail="AI 未配置")
    ctx = req.context or _lesson_text(db, req.lesson_id)
    if not ctx:
        raise HTTPException(status_code=400, detail="该课文暂无内容")
    system = (
        "你是小学生的学习助手，正在主动提问。请针对下面这段课文，"
        "一次性提出 1-4 个只有学生能补充的高信息量诊断性问题，不要重复已知信息。"
        '只返回 JSON：{"intro":"简短引导语","questions":[{"id":"q1","prompt":"问题",'
        '"options":[{"label":"选项"}]}]}。选项可为空数组，表示自由作答。'
    )
    raw = provider.generate(prompt=f"课文：\n{ctx[:6000]}", system=system, json_mode=True)
    try:
        data = json.loads(raw)
        return {"intro": data.get("intro", ""), "questions": data.get("questions") or []}
    except (ValueError, TypeError):
        raise HTTPException(status_code=502, detail="AI 返回无法解析")


@router.post("/ask/reply")
def ask_reply(req: AskReplyReq, db: Session = Depends(get_db)):
    from ..services.ai import get_provider
    provider = get_provider(db)
    if provider.name == "fake":
        raise HTTPException(status_code=503, detail="AI 未配置")
    ctx = req.context or _lesson_text(db, req.lesson_id)
    replies_text = json.dumps(req.replies, ensure_ascii=False)
    prompt = (
        f"教材上下文（按句切分，句前编号）：{ctx}\n"
        f"学生对这些诊断性问题的回答：{replies_text}\n"
        "请基于学生的回答，继续用小学生能懂的话讲解课文。"
        "如果讲解涉及原文某一句，在那句后标 [第N句]。"
    )
    answer = provider.generate(prompt=prompt, system="你是小学生的学习助手。")
    import re as _re
    citations = [int(n) for n in _re.findall(r"第\s*(\d+)\s*句", answer)]
    return {"answer": answer, "citations": sorted(set(citations))}
