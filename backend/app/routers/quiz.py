"""边读边问：测验（quiz）与主动提问（ask questions）。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Quiz, Text, KnowledgePoint, Lesson
from ..services.quiz import grade_answers, strip_key

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
    from ..tools.generation import generate_quiz_questions
    from ..core.context import UnifiedContext
    text = _lesson_text(db, req.lesson_id)
    if not text:
        raise HTTPException(status_code=400, detail="该课文暂无内容，无法出题")
    kps = [{"id": k.id, "category": k.category, "content": k.content}
           for k in db.query(KnowledgePoint).filter_by(lesson_id=req.lesson_id).all()]
    lesson = db.get(Lesson, req.lesson_id)
    subject = (lesson.subject if lesson else "语文") or "语文"
    ctx = UnifiedContext(user_id=req.user_id, lesson_id=req.lesson_id, question="")
    result = generate_quiz_questions.run(
        {
            "text": text,
            "n": 3,
            "knowledge_points": json.dumps(kps, ensure_ascii=False),
            "subject": subject,
        },
        ctx,
    )
    if not result.get("questions"):
        raise HTTPException(status_code=503, detail=result.get("error", "AI 未配置"))
    quiz = Quiz(lesson_id=req.lesson_id, user_id=req.user_id,
                questions=json.dumps(result["questions"], ensure_ascii=False))
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return {"quiz_id": quiz.id, "questions": strip_key(result["questions"])}


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
    # 题目里的知识点 id 由 AI 选出，可能已被删除或是编造的；只认库里存在的
    kp_ids = {q.get("knowledge_point_id") for q in questions if isinstance(q.get("knowledge_point_id"), int)}
    valid_kp = {r[0] for r in db.query(KnowledgePoint.id).filter(KnowledgePoint.id.in_(kp_ids)).all()} if kp_ids else set()
    for q in questions:
        if q.get("knowledge_point_id") not in valid_kp:
            q["knowledge_point_id"] = None
    if quiz.user_id:
        from ..services.mastery import record_attempt as record_mastery
        for q, r in zip(questions, results):
            kpid = q.get("knowledge_point_id")
            if kpid is not None:
                record_mastery(db, quiz.user_id, "knowledge", kpid, r["is_correct"])
    if quiz.user_id:
        from ..services.quiz import record_quiz_mistake
        for q, r in zip(questions, results):
            if r["is_correct"]:
                continue
            sel = next((a.get("selected_index") for a in req.answers
                        if a.get("question_id") == q["id"]), None)
            your = (q["choices"][sel]
                    if isinstance(sel, int) and 0 <= sel < len(q["choices"]) else "")
            correct = q["choices"][q["correct_index"]]
            record_quiz_mistake(db, quiz.user_id, q["prompt"], your, correct,
                                q.get("knowledge_point_id"))
    score = sum(1 for r in results if r["is_correct"])
    quiz.score = score
    db.commit()
    return {"answers": results, "score": score, "total": len(questions)}


@router.post("/ask/questions")
def ask_questions(req: AskQuestionsReq, db: Session = Depends(get_db)):
    from ..tools.generation import generate_diagnostic_questions
    from ..core.context import UnifiedContext
    ctx_text = req.context or _lesson_text(db, req.lesson_id)
    if not ctx_text:
        raise HTTPException(status_code=400, detail="该课文暂无内容")
    lesson = db.get(Lesson, req.lesson_id)
    subject = (lesson.subject if lesson else "语文") or "语文"
    ctx = UnifiedContext(user_id=0, lesson_id=req.lesson_id, question="")
    result = generate_diagnostic_questions.run({"context": ctx_text, "subject": subject}, ctx)
    if not result["questions"]:
        raise HTTPException(status_code=503, detail="AI 未配置")
    return {"intro": result["intro"], "questions": result["questions"]}


@router.post("/ask/reply")
async def ask_reply(req: AskReplyReq, db: Session = Depends(get_db)):
    from ..core.context import UnifiedContext
    from ..runtime.orchestrator import route_to_capability
    from ..models import User
    ctx_text = req.context or _lesson_text(db, req.lesson_id)
    replies_text = json.dumps(req.replies, ensure_ascii=False)
    # 与 /api/ask 一致：尚无鉴权，先取第一个孩子作占位用户
    child = db.query(User).filter_by(role="child").first()
    ctx = UnifiedContext(
        user_id=child.id if child else 0, lesson_id=req.lesson_id,
        question=f"学生对这些诊断性问题的回答：{replies_text}，请基于回答继续用小学生能懂的话讲解课文，涉及原文某句时在那句后标 [第N句]。",
        text=ctx_text,
        mode="chat",
    )
    return await route_to_capability(ctx)
