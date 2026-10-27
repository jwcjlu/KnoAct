from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from ..models import Lesson, WordBank, Point
from ..models import KnowledgePoint, Mistake, WordMastery
from ..services.scheduler import select_words, next_review_after
from ..services.ai import get_provider

router = APIRouter(tags=["learning"])

MASTERY_REMOVE_AFTER = 3  # 连续答对 3 次视为已掌握，移出日常听写


@router.get("/api/dictation/words")
def dictation_words(user_id: int, db: Session = Depends(get_db)):
    approved = db.query(Lesson).filter_by(audit_status="approved").all()
    ids = [l.id for l in approved]
    words = db.query(WordBank).filter(WordBank.lesson_id.in_(ids)).all() if ids else []
    # 读 mastery：错得多/到期 的排前面
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
def dictation_grade(req: GradeReq, db: Session = Depends(get_db)):
    correct = req.answer.strip() == req.word.strip()
    # 更新掌握度（按词条匹配或 word_id 定位）
    w = None
    if req.word_id:
        w = db.get(WordBank, req.word_id)
    else:
        w = db.query(WordBank).filter_by(word=req.word).first()
    if w:
        from ..services.mastery import record_attempt as record_mastery
        record_mastery(db, req.user_id, "word", w.id, correct)
    return {"correct": correct}

class WrongWord(BaseModel):
    word: str
    your_answer: str = ""

class CompleteReq(BaseModel):
    user_id: int
    correct: int
    wrong: int
    wrong_words: list[WrongWord] = []

@router.post("/api/dictation/complete")
def dictation_complete(req: CompleteReq, db: Session = Depends(get_db)):
    awarded = max(req.correct * 2, 10)
    db.add(Point(user_id=req.user_id, delta=awarded, reason="听写打卡"))
    # 错词自动收录进错题本
    for ww in req.wrong_words:
        db.add(Mistake(
            user_id=req.user_id, source_type="dictation",
            question=f"听写词语：{ww.word}",
            your_answer=ww.your_answer, correct_answer=ww.word,
        ))
    db.commit()
    return {"points_awarded": awarded, "mistakes_recorded": len(req.wrong_words)}

@router.get("/api/review/questions")
def review_questions(subject: str, db: Session = Depends(get_db)):
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
def review_submit(req: ReviewSubmitReq, db: Session = Depends(get_db)):
    if req.your_answer.strip() != req.correct_answer.strip():
        db.add(Mistake(
            user_id=req.user_id, source_type=req.source_type,
            question=req.question, your_answer=req.your_answer, correct_answer=req.correct_answer,
        ))
        db.commit()
    return {"ok": True}

@router.get("/api/listening/material")
def listening_material(user_id: int, db: Session = Depends(get_db)):
    from ..tools.generation import generate_listening
    from ..core.context import UnifiedContext
    ctx = UnifiedContext(user_id=user_id, lesson_id=0, question="")
    result = generate_listening.run({}, ctx)
    return {
        "text": result["dialogue"],
        "questions": [{"question": result["question"], "answer": result["answer"]}],
    }

@router.get("/api/reading/material")
def reading_material(lesson_id: int, db: Session = Depends(get_db)):
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
