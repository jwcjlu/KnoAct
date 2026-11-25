"""边读边问：测验（quiz）与主动提问（ask questions）。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import ensure_lesson_document_access, ensure_user_access, require_learning_user
from ..database import get_db
from ..models import Quiz, Text, KnowledgePoint, Lesson, User
from ..services.quiz import grade_answers, grade_verdict, strip_key, verdict_evidence_ok
from ..services.answer_record import record_answer
from ..services.bucket_guard import resolve_bucket_id

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
def quiz_generate(req: QuizGenerateReq, user: User = Depends(require_learning_user),
                  db: Session = Depends(get_db)):
    uid = req.user_id or user.id
    if req.user_id:
        ensure_user_access(user, req.user_id, db)
    viewer = db.get(User, uid)
    if viewer is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    ensure_lesson_document_access(viewer, req.lesson_id, db)
    from ..tools.generation import generate_quiz_questions
    from ..core.context import UnifiedContext
    text = _lesson_text(db, req.lesson_id)
    if not text:
        raise HTTPException(status_code=400, detail="该课文暂无内容，无法出题")
    kps = [{"id": k.id, "category": k.category, "content": k.content}
           for k in db.query(KnowledgePoint).filter_by(lesson_id=req.lesson_id).all()]
    lesson = db.get(Lesson, req.lesson_id)
    subject = (lesson.subject if lesson else "语文") or "语文"
    ctx = UnifiedContext(user_id=uid, lesson_id=req.lesson_id, question="")
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
    quiz = Quiz(lesson_id=req.lesson_id, user_id=uid,
                bucket_id=resolve_bucket_id(db, uid, None),
                questions=json.dumps(result["questions"], ensure_ascii=False))
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return {"quiz_id": quiz.id, "questions": strip_key(result["questions"])}


@router.post("/quiz/submit")
def quiz_submit(req: QuizSubmitReq, user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    quiz = db.get(Quiz, req.quiz_id)
    if not quiz:
        raise HTTPException(status_code=409, detail="测验已过期")
    if quiz.user_id:
        ensure_user_access(user, quiz.user_id, db)
        sub = db.get(User, quiz.user_id)
        if sub:
            ensure_lesson_document_access(sub, quiz.lesson_id, db)
    else:
        ensure_lesson_document_access(user, quiz.lesson_id, db)
    questions = json.loads(quiz.questions)
    valid_ids = {q["id"] for q in questions}
    for a in req.answers:
        if a.get("question_id") not in valid_ids:
            raise HTTPException(status_code=409, detail="测验已过期")
        if not isinstance(a.get("selected_index"), int):
            raise HTTPException(status_code=422, detail="选项无效")
    results = grade_answers(questions, req.answers)
    result_by_qid = {r["question_id"]: r for r in results if r.get("question_id") is not None}
    # 答 + 指：把每条答案的出处与题目 evidence 比较，产出四态 verdict
    chosen_by_qid = {a.get("question_id"): (a.get("evidence_sentence") or "").strip()
                     for a in req.answers}
    q_by_id = {q["id"]: q for q in questions}
    for r in results:
        q = q_by_id.get(r.get("question_id")) or {}
        chosen = chosen_by_qid.get(r.get("question_id"), "")
        verdict = grade_verdict(
            answer_correct=r["is_correct"] is True,
            chosen_evidence=chosen,
            correct_evidence=q.get("evidence") or "",
        )
        r["verdict"] = verdict
        r["evidence_ok"] = verdict_evidence_ok(verdict)
    # 题目里的知识点 id 由 AI 选出，可能已被删除或是编造的；只认库里存在的
    kp_ids = {q.get("knowledge_point_id") for q in questions if isinstance(q.get("knowledge_point_id"), int)}
    valid_kp = {r[0] for r in db.query(KnowledgePoint.id).filter(KnowledgePoint.id.in_(kp_ids)).all()} if kp_ids else set()
    for q in questions:
        if q.get("knowledge_point_id") not in valid_kp:
            q["knowledge_point_id"] = None
    if quiz.user_id:
        from ..services.mastery import record_attempt as record_mastery
        for q in questions:
            r = result_by_qid.get(q["id"])
            if r is None:
                continue
            kpid = q.get("knowledge_point_id")
            if kpid is not None:
                record_mastery(db, quiz.user_id, "knowledge", kpid, r["is_correct"],
                               bucket_id=quiz.bucket_id)
    if quiz.user_id:
        from ..services.quiz import record_quiz_mistake
        lesson = db.get(Lesson, quiz.lesson_id)
        subject = (lesson.subject if lesson else "") or ""
        for q in questions:
            r = result_by_qid.get(q["id"])
            if r is None:
                continue
            sel = next((a.get("selected_index") for a in req.answers
                        if a.get("question_id") == q["id"]), None)
            your = (q["choices"][sel]
                    if isinstance(sel, int) and 0 <= sel < len(q["choices"]) else "")
            correct = q["choices"][q["correct_index"]]
            record_answer(
                db, user_id=quiz.user_id, subject=subject, module="quiz",
                lesson_id=quiz.lesson_id,
                question=q["prompt"], student_answer=your,
                correct_answer=correct, is_correct=r["is_correct"] is True,
                source_type="quiz", source_id=q["id"],
                duration_ms=next((a.get("duration_ms") for a in req.answers
                                  if a.get("question_id") == q["id"]), None),
                evidence_text=chosen_by_qid.get(q["id"], ""),
                evidence_ok=r["evidence_ok"],
                bucket_id=quiz.bucket_id,
            )
            # 理解对、表达没到位（expression_weak）不进错题本：
            # 他要的是帮他把话说清楚，不是再刷同类题。
            if not r["is_correct"] and r.get("verdict") != "expression_weak":
                record_quiz_mistake(db, quiz.user_id, q["prompt"], your, correct,
                                    q.get("knowledge_point_id"),
                                    bucket_id=quiz.bucket_id)
    score = sum(1 for r in results if r["is_correct"])
    quiz.score = score
    db.commit()
    return {"answers": results, "score": score, "total": len(questions)}


@router.post("/ask/questions")
def ask_questions(req: AskQuestionsReq, user: User = Depends(require_learning_user),
                  db: Session = Depends(get_db)):
    ensure_lesson_document_access(user, req.lesson_id, db)
    from ..tools.generation import generate_diagnostic_questions
    from ..core.context import UnifiedContext
    ctx_text = req.context or _lesson_text(db, req.lesson_id)
    if not ctx_text:
        raise HTTPException(status_code=400, detail="该课文暂无内容")
    lesson = db.get(Lesson, req.lesson_id)
    subject = (lesson.subject if lesson else "语文") or "语文"
    ctx = UnifiedContext(user_id=user.id, lesson_id=req.lesson_id, question="")
    result = generate_diagnostic_questions.run({"context": ctx_text, "subject": subject}, ctx)
    if not result["questions"]:
        raise HTTPException(status_code=503, detail="AI 未配置")
    return {"intro": result["intro"], "questions": result["questions"]}


@router.post("/ask/reply")
async def ask_reply(req: AskReplyReq, user: User = Depends(require_learning_user),
                    db: Session = Depends(get_db)):
    ensure_lesson_document_access(user, req.lesson_id, db)
    from ..core.context import UnifiedContext
    from ..runtime.orchestrator import route_to_capability
    ctx_text = req.context or _lesson_text(db, req.lesson_id)
    replies_text = json.dumps(req.replies, ensure_ascii=False)
    ctx = UnifiedContext(
        user_id=user.id, lesson_id=req.lesson_id,
        question=f"学生对这些诊断性问题的回答：{replies_text}，请基于回答继续用小学生能懂的话讲解课文，涉及原文某句时在那句后标 [第N句]。",
        text=ctx_text,
        mode="chat",
    )
    return await route_to_capability(ctx)
