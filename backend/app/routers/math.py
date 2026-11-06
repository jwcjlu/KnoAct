"""数学练习：出题（计算/应用题）+ 数值判分。"""
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import ensure_lesson_document_access, ensure_user_access, require_learning_user
from ..database import get_db
from ..models import Text, Question, Mistake, Task, User

router = APIRouter(prefix="/api/math", tags=["math"])


def _record_mistake(db: Session, user_id: int, question: str, user_ans: str, correct_answer: str,
                    bucket_id: int | None = None):
    """答错收错题本（source_type=math），按题面去重累加。"""
    existing = db.query(Mistake).filter_by(user_id=user_id, question=question,
                                           bucket_id=bucket_id).first()
    if existing:
        existing.mistake_count += 1
        existing.consecutive_correct = 0
    else:
        db.add(Mistake(
            user_id=user_id, source_type="math",
            question=question, your_answer=user_ans,
            correct_answer=correct_answer,
            bucket_id=bucket_id,
        ))


@router.get("/material")
def math_material(lesson_id: int, user: User = Depends(require_learning_user),
                  db: Session = Depends(get_db)):
    ensure_lesson_document_access(user, lesson_id, db)
    from ..services.math_gen import generate_math_questions
    from ..models import Lesson
    lesson = db.get(Lesson, lesson_id)
    title = lesson.title if lesson else ""
    t = db.query(Text).filter_by(lesson_id=lesson_id).first()
    if not t:
        return {"title": title, "text": "", "questions": []}
    qs = db.query(Question).filter_by(lesson_id=lesson_id, qtype="math").order_by(Question.id).all()
    if not qs:
        # 无预生成题时现场生成并落库（首次慢一次，之后命中缓存）
        gen = generate_math_questions(db, t.content, n=3)
        for q in gen:
            db.add(Question(lesson_id=lesson_id, qtype="math", question=q["question"], answer=q["answer"]))
        db.commit()
        qs = db.query(Question).filter_by(lesson_id=lesson_id, qtype="math").order_by(Question.id).all()
    return {"title": title, "text": t.content, "questions": [{"id": q.id, "question": q.question, "answer": q.answer} for q in qs]}


class GradeReq(BaseModel):
    user_id: int
    lesson_id: int
    answers: list[dict]  # [{question_id, answer}]


@router.post("/grade")
def math_grade(req: GradeReq, user: User = Depends(require_learning_user),
               db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    from ..services.math_gen import grade_math_answer
    from ..services.bucket_guard import resolve_bucket_id
    bid = resolve_bucket_id(db, req.user_id, None)
    questions = db.query(Question).filter_by(lesson_id=req.lesson_id, qtype="math").all()
    by_id = {q.id: q for q in questions}
    results = []
    for a in req.answers:
        q = by_id.get(a.get("question_id"))
        if q is None:
            results.append({"question_id": a.get("question_id"), "is_correct": False, "correct_answer": ""})
            continue
        user_ans = str(a.get("answer") or "")
        is_correct = grade_math_answer(user_ans, q.answer)
        results.append({"question_id": q.id, "is_correct": is_correct, "correct_answer": q.answer})
        if not is_correct:
            _record_mistake(db, req.user_id, q.question, user_ans, q.answer, bucket_id=bid)
    db.commit()
    return {"results": results, "correct": sum(1 for r in results if r["is_correct"]),
            "total": len(results)}


class TaskGradeReq(BaseModel):
    user_id: int
    answers: list[str]  # 按题目顺序


@router.post("/task/{task_id}/grade")
def math_task_grade(task_id: int, req: TaskGradeReq, user: User = Depends(require_learning_user),
                    db: Session = Depends(get_db)):
    """首页「数学练习」任务判分：题目来自 Task.content（[{question, answer}]）。"""
    from ..services.math_gen import grade_math_answer
    from ..services.bucket_guard import resolve_bucket_id
    ensure_user_access(user, req.user_id, db)
    bid = resolve_bucket_id(db, req.user_id, None)
    task = db.get(Task, task_id)
    if not task or task.task_type != "math":
        return {"ok": False, "error": "任务不存在"}
    ensure_user_access(user, task.user_id, db)
    if task.submit_status == "approved":
        return {"ok": False, "error": "家长已确认，不能再修改"}
    try:
        questions = json.loads(task.content or "[]")
    except ValueError:
        questions = []
    results = []
    for i, q in enumerate(questions):
        user_ans = req.answers[i] if i < len(req.answers) else ""
        is_correct = grade_math_answer(user_ans, q.get("answer", ""))
        results.append({"is_correct": is_correct, "correct_answer": q.get("answer", "")})
        # 作答写回任务快照，家长确认前可重新打开修改
        q["your_answer"] = user_ans
        q["is_correct"] = is_correct
        if not is_correct:
            _record_mistake(db, req.user_id, q.get("question", ""), user_ans, q.get("answer", ""),
                            bucket_id=bid)
    task.content = json.dumps(questions, ensure_ascii=False)
    db.commit()
    return {"ok": True, "results": results,
            "correct": sum(1 for r in results if r["is_correct"]), "total": len(results)}
