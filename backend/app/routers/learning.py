import base64 as _base64

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from ..core.access import (
    ensure_lesson_document_access,
    ensure_user_access,
    require_learning_user,
    resolve_target_user_id,
)
from ..database import get_db
from ..models import Lesson, WordBank, Point, User
from ..models import KnowledgePoint, Mistake, WordMastery, LearningProgress
from ..services.scheduler import select_words, next_review_after
from ..services.ai import get_provider
from ..services.bucket_guard import resolve_bucket_id

router = APIRouter(tags=["learning"])

MASTERY_REMOVE_AFTER = 3  # 连续答对 3 次视为已掌握，移出日常听写


def _cfg_int(db, key, fallback, child_id=None):
    from ..services.child_config import get_child_config_int
    if child_id is None:
        from ..models import ModelConfig
        row = db.query(ModelConfig).filter_by(key=key).first()
        try:
            return int(row.value) if row and row.value else fallback
        except ValueError:
            return fallback
    return get_child_config_int(db, child_id, key, fallback)


def _cfg_str(db, key, fallback, child_id=None):
    from ..services.child_config import get_child_config_str
    if child_id is None:
        from ..models import ModelConfig
        row = db.query(ModelConfig).filter_by(key=key).first()
        return row.value if row and row.value else fallback
    return get_child_config_str(db, child_id, key, fallback)


@router.get("/api/dictation/words")
def dictation_words(subject: str = "语文",
                    user_id: int = Depends(resolve_target_user_id),
                    _user: User = Depends(require_learning_user),
                    db: Session = Depends(get_db)):
    # 只取当前课的生词（与 task_gen._current_lesson 口径一致），而非全库所有已审核课
    prog = db.query(LearningProgress).filter_by(user_id=user_id, subject=subject).first()
    lessons = db.query(Lesson).filter_by(subject=subject).order_by(Lesson.id).all()
    lesson = None
    if lessons:
        if prog and prog.current_lesson_id:
            lesson = next((l for l in lessons if l.id == prog.current_lesson_id), None)
        lesson = lesson or lessons[0]
    if lesson is None:
        return []
    words = db.query(WordBank).filter_by(lesson_id=lesson.id).all()
    rows = []
    for w in words:
        m = db.query(WordMastery).filter_by(word_bank_id=w.id).first()
        rows.append({
            "id": w.id, "word": w.word, "extra": w.extra,
            "mistake_count": m.mistake_count if m else 0,
            "next_review_at": m.next_review_at if m else None,
            "mastered": m is not None and m.correct_count >= MASTERY_REMOVE_AFTER,
        })
    picked = select_words([r for r in rows if not r["mastered"]], limit=len(rows), now=datetime.utcnow())
    return [{"id": r["id"], "word": r["word"], "extra": r["extra"]} for r in picked]


class GradeReq(BaseModel):
    user_id: int = 0
    word: str
    word_id: int = 0
    answer: str


@router.post("/api/dictation/grade")
def dictation_grade(req: GradeReq, user: User = Depends(require_learning_user),
                    db: Session = Depends(get_db)):
    uid = req.user_id or user.id
    if req.user_id:
        ensure_user_access(user, req.user_id, db)
    correct = req.answer.strip() == req.word.strip()
    # 更新掌握度（按词条匹配或 word_id 定位）
    w = None
    if req.word_id:
        w = db.get(WordBank, req.word_id)
    else:
        w = db.query(WordBank).filter_by(word=req.word).first()
    if w:
        from ..services.mastery import record_attempt as record_mastery
        # user_id 是可空外键：未传（0）时存 NULL
        bid = resolve_bucket_id(db, uid, None) if uid else None
        record_mastery(db, uid or None, "word", w.id, correct,
                       bucket_id=bid)
    return {"correct": correct}

class WrongWord(BaseModel):
    word: str
    your_answer: str = ""
    word_id: int = 0

class CompleteReq(BaseModel):
    user_id: int
    correct: int
    wrong: int
    wrong_words: list[WrongWord] = []

@router.post("/api/dictation/complete")
def dictation_complete(req: CompleteReq, user: User = Depends(require_learning_user),
                       db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    awarded = max(req.correct * 2, 10)
    bid = resolve_bucket_id(db, req.user_id, None)
    db.add(Point(user_id=req.user_id, delta=awarded, reason="听写打卡",
                 bucket_id=bid))
    # 错词自动收录进错题本
    for ww in req.wrong_words:
        db.add(Mistake(
            user_id=req.user_id, source_type="dictation",
            question=f"听写词语：{ww.word}",
            your_answer=ww.your_answer, correct_answer=ww.word,
            word_bank_id=ww.word_id if ww.word_id else None,
            bucket_id=bid,
        ))
    db.commit()
    return {"points_awarded": awarded, "mistakes_recorded": len(req.wrong_words)}

@router.get("/api/review/questions")
def review_questions(subject: str, user_id: int = Depends(resolve_target_user_id),
                     _auth: User = Depends(require_learning_user),
                     db: Session = Depends(get_db)):
    points = db.query(KnowledgePoint).filter_by(subject=subject).all()
    provider = get_provider(db)
    if not points:
        return []
    questions = []
    for p in points[:5]:
        try:
            q = provider.generate(
                prompt=f"针对知识点「{p.content}」出一道判断正误题，格式：题目||答案",
                system="你是出题老师，只输出题目和答案，用||分隔。",
            )
            stem, ans = q.split("||") if "||" in q else (q, "")
        except Exception:
            stem, ans = f"「{p.content}」的判断对错题（示例）", "对"
        questions.append({"question": stem, "answer": ans, "point_id": p.id})
    return questions

class ReviewSubmitReq(BaseModel):
    user_id: int
    question: str
    your_answer: str
    correct_answer: str
    source_type: str = "review"

@router.post("/api/review/submit")
def review_submit(req: ReviewSubmitReq, user: User = Depends(require_learning_user),
                  db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    if req.your_answer.strip() != req.correct_answer.strip():
        bid = resolve_bucket_id(db, req.user_id, None)
        db.add(Mistake(
            user_id=req.user_id, source_type=req.source_type,
            question=req.question, your_answer=req.your_answer, correct_answer=req.correct_answer,
            bucket_id=bid,
        ))
        db.commit()
    return {"ok": True}

@router.get("/api/listening/material")
def listening_material(user_id: int = Depends(resolve_target_user_id),
                       _user: User = Depends(require_learning_user),
                       db: Session = Depends(get_db)):
    import json as _json
    from datetime import date as _date
    from ..models import Task
    from ..tools.generation import generate_listening
    from ..core.context import UnifiedContext

    row = db.query(Task).filter_by(
        user_id=user_id, subject="英语", date=_date.today(), task_type="listening"
    ).order_by(Task.id).first()
    if row and row.content:
        try:
            data = _json.loads(row.content)
            if data.get("dialogue"):
                return {
                    "text": data["dialogue"],
                    "questions": [{"question": data.get("question", ""), "answer": data.get("answer", "")}],
                }
        except Exception:
            pass

    ctx = UnifiedContext(user_id=user_id, lesson_id=0, question="")
    result = generate_listening.run({}, ctx)
    content = _json.dumps(result, ensure_ascii=False)
    if row is not None:
        # 已存在当天 listening Task 但内容空/无法解析：原地更新，避免撞唯一约束
        row.content = content
        row.title = "英语听力练习"
        row.content_status = "published"
    else:
        db.add(Task(
            user_id=user_id, subject="英语", date=_date.today(), task_type="listening",
            title="英语听力练习", content_status="published", content=content,
        ))
    db.commit()
    return {
        "text": result["dialogue"],
        "questions": [{"question": result["question"], "answer": result["answer"]}],
    }

@router.get("/api/reading/material")
def reading_material(lesson_id: int, user_id: int = Depends(resolve_target_user_id),
                     _auth: User = Depends(require_learning_user),
                     db: Session = Depends(get_db)):
    viewer = db.get(User, user_id)
    if viewer is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    ensure_lesson_document_access(viewer, lesson_id, db)
    from ..models import Text, Question
    from ..services.question_gen import generate_reading_questions
    t = db.query(Text).filter_by(lesson_id=lesson_id).first()
    if not t:
        return {"text": "", "questions": []}
    qs = db.query(Question).filter_by(lesson_id=lesson_id, qtype="reading").order_by(Question.id).all()
    if not qs:
        # 兼容历史数据：无预生成题时现场生成并落库（首次仍慢一次，之后命中缓存）
        gen = generate_reading_questions(db, t.content, n=1)
        for q in gen:
            db.add(Question(lesson_id=lesson_id, qtype="reading", question=q["question"], answer=q["answer"]))
        db.commit()
        qs = db.query(Question).filter_by(lesson_id=lesson_id, qtype="reading").order_by(Question.id).all()
    return {"text": t.content, "questions": [{"question": q.question, "answer": q.answer} for q in qs]}


@router.get("/api/learning/lessons")
def learning_lessons(subject: str = "语文",
                     user_id: int = Depends(resolve_target_user_id),
                     _auth: User = Depends(require_learning_user),
                     db: Session = Depends(get_db)):
    """个性化学习选课列表：返回该学科所有课（含教材来源、当前进度标记）。"""
    from ..models import PdfDocument
    lessons = db.query(Lesson).filter_by(subject=subject).order_by(Lesson.id).all()
    prog = db.query(LearningProgress).filter_by(user_id=user_id, subject=subject).first()
    current_id = prog.current_lesson_id if prog else None
    out = []
    for l in lessons:
        doc = db.get(PdfDocument, l.document_id)
        out.append({
            "id": l.id, "subject": l.subject, "title": l.title,
            "start_page": l.start_page, "end_page": l.end_page,
            "document_name": doc.filename if doc else "",
            "is_current": l.id == current_id,
        })
    return out


class AssignmentReq(BaseModel):
    user_id: int
    lesson_id: int
    subject: str = "语文"
    previous_questions: list[str] = []  # 本课已出过的题，新一组不重复
    wrong_questions: list[str] = []     # 上一组答错的题，新一组围绕同类内容再考


@router.post("/api/learning/assignment")
def assignment(req: AssignmentReq, user: User = Depends(require_learning_user),
               db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    """AI 现场出作业：读配置的题数与难度，基于本课正文出题，并关联本课知识点。"""
    from ..models import Text
    from ..services.assignment import generate_assignment
    t = db.query(Text).filter_by(lesson_id=req.lesson_id).first()
    if not t or not t.content.strip():
        return {"questions": []}
    kps = db.query(KnowledgePoint).filter_by(lesson_id=req.lesson_id).all()
    knowledge_points = [{"id": p.id, "category": p.category, "content": p.content} for p in kps]
    n = _cfg_int(db, "assignment_question_count", 4)
    diff = _cfg_str(db, f"difficulty_{req.subject}", "中等")
    qs = generate_assignment(db, t.content, subject=req.subject, difficulty=diff, n=n,
                             knowledge_points=knowledge_points,
                             previous_questions=req.previous_questions,
                             wrong_questions=req.wrong_questions)
    return {"questions": qs}


class AssignmentGradeReq(BaseModel):
    user_id: int
    lesson_id: int
    subject: str = "语文"
    answers: list[dict] = []  # 兼容旧调用：[{knowledge_point_id: int|null, is_correct: bool}]
    items: list[dict] = []    # 服务端判分：[{question, answer, student_answer, knowledge_point_id}]


@router.post("/api/learning/assignment/grade")
def assignment_grade(req: AssignmentGradeReq, user: User = Depends(require_learning_user),
                     db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    """判分：正确率 >= 阈值则推进进度；逐题落知识点掌握度（驱动遗忘曲线）。

    传 items 时由服务端（AI）逐题判对错并返回参考答案与讲解；否则沿用 answers 里的 is_correct。
    """
    from ..services.mastery import record_attempt
    from ..services.assignment import grade_assignment
    try:
        threshold = float(_cfg_str(db, "assignment_pass_threshold", "0.6"))
    except ValueError:
        threshold = 0.6
    results = []
    answers = req.answers
    if req.items:
        graded = grade_assignment(db, req.items)
        answers = []
        for it, g in zip(req.items, graded):
            answers.append({"knowledge_point_id": it.get("knowledge_point_id"), "is_correct": g["is_correct"]})
            results.append({"question": it.get("question", ""), "answer": it.get("answer", ""),
                             "student_answer": it.get("student_answer", ""),
                             "is_correct": g["is_correct"], "feedback": g["feedback"]})
    total = len(answers)
    correct = sum(1 for a in answers if a.get("is_correct"))
    rate = correct / total if total else 0
    passed = rate >= threshold
    # 无论通过与否，逐题落知识点掌握度（掌握度反映真实答题历史）
    # 知识点 id 来自 AI 出题，只认库里存在的
    kp_ids = {a.get("knowledge_point_id") for a in answers if isinstance(a.get("knowledge_point_id"), int)}
    valid_kp = {r[0] for r in db.query(KnowledgePoint.id).filter(KnowledgePoint.id.in_(kp_ids)).all()} if kp_ids else set()
    bid = resolve_bucket_id(db, req.user_id, None)
    for a in answers:
        kpid = a.get("knowledge_point_id")
        if kpid in valid_kp:
            record_attempt(db, req.user_id, "knowledge", kpid, bool(a.get("is_correct")),
                           bucket_id=bid)
    if passed:
        lessons = db.query(Lesson).filter_by(subject=req.subject).order_by(Lesson.id).all()
        prog = db.query(LearningProgress).filter_by(user_id=req.user_id, subject=req.subject).first()
        if not prog:
            prog = LearningProgress(user_id=req.user_id, subject=req.subject, current_lesson_id=None)
            db.add(prog)
        if lessons:
            ids = [l.id for l in lessons]
            cur = prog.current_lesson_id
            if cur in ids:
                idx = ids.index(cur)
                nxt = ids[idx + 1] if idx + 1 < len(ids) else ids[-1]
            else:
                nxt = ids[0]
            prog.current_lesson_id = nxt
        db.commit()
    return {"passed": passed, "rate": rate, "threshold": threshold,
            "correct": correct, "total": total, "results": results}


class GradeHandwritingReq(BaseModel):
    user_id: int
    words: list[dict] = []   # [{index, word}]
    image_base64: str = ""


@router.post("/api/dictation/grade-handwriting")
def grade_handwriting_endpoint(req: GradeHandwritingReq, user: User = Depends(require_learning_user),
                               db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    from ..services.handwriting import grade_handwriting
    image_bytes = _base64.b64decode(req.image_base64) if req.image_base64 else b""
    results = grade_handwriting(db, image_bytes, req.words)
    return {"results": results}


class AppealReq(BaseModel):
    user_id: int
    word: str
    word_id: int = 0
    reason: str = ""


@router.post("/api/dictation/appeal")
def appeal(req: AppealReq, user: User = Depends(require_learning_user),
           db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    """孩子申诉：某词批改有误，标记待复核。"""
    # 本阶段简化：记录申诉到 Mistake 表（source_type="appeal"）或直接返回 ok
    # 家长复核 UI 是后续，这里先落一条记录供家长端查询
    from ..models import Mistake
    bid = resolve_bucket_id(db, req.user_id, None)
    db.add(Mistake(
        user_id=req.user_id, source_type="appeal",
        question=f"听写申诉：{req.word}",
        your_answer=req.reason or "（未说明原因）",
        correct_answer=req.word,
        word_bank_id=req.word_id if req.word_id else None,
        bucket_id=bid,
    ))
    db.commit()
    return {"ok": True}
