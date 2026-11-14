"""任务接口：列/审核/改/删/增/提交/上传/确认。"""
import json
import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access, require_learning_user, resolve_target_user_id
from ..core.deps import require_role
from ..database import get_db
from ..models import Task, Point, User
from ..services.task_gen import generate_tasks_for_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 5 * 1024 * 1024  # 5MB


class ApproveAllReq(BaseModel):
    user_id: int
    date: date


class EditReq(BaseModel):
    title: str = ""
    detail: str = ""
    content: str = ""


class KnowledgeReviewReq(BaseModel):
    user_id: int
    answers: list[dict] = []   # [{id: 知识点id, user_answer: 孩子答案}]


class AddReq(BaseModel):
    user_id: int
    date: date
    subject: str = "语文"
    task_type: str = "custom"
    title: str = ""
    detail: str = ""
    content: str = ""
    points: int = 20


def _dictation_photo_required(db: Session, t: Task) -> bool:
    if t.task_type != "dictation":
        return False
    from ..services.child_config import get_dictation_input_mode

    if get_dictation_input_mode(db, t.user_id) != "paper_photo":
        return False
    return not (t.photo_path or "").strip()


def _raise_photo_required() -> None:
    raise HTTPException(
        status_code=400,
        detail={"error": "photo_required", "message": "请先上传听写打卡照片"},
    )


def _math_submit_blocked(db: Session, t: Task) -> None:
    if t.task_type != "math":
        return
    from ..services.math_gen import math_content_ready_to_submit, parse_math_task_content

    parsed = parse_math_task_content(t.content or "")
    ok, code = math_content_ready_to_submit(parsed)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail={"error": code, "message": "请先完成全部计算题判分并上传应用题照片"},
        )


_PHOTO_AI_KEYS = (
    "final_answer", "steps_plausible", "confidence", "reason",
    "ai_status", "ai_correct", "ai_notes",
)


def _to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "subject": t.subject,
        "task_type": t.task_type,
        "title": t.title,
        "detail": t.detail,
        "content": t.content,
        "points": t.points,
        "content_status": t.content_status,
        "submit_status": t.submit_status,
        "photo_path": t.photo_path,
    }


@router.get("")
def list_tasks(date: date, role: str = "child", bucket_id: int | None = None,
               user_id: int = Depends(resolve_target_user_id),
               _user: User = Depends(require_learning_user), db: Session = Depends(get_db)):
    from ..services.bucket_guard import resolve_bucket_id
    bid = resolve_bucket_id(db, user_id, bucket_id)
    q = db.query(Task).filter_by(user_id=user_id, date=date)
    if bid is not None:
        q = q.filter_by(bucket_id=bid)
    if role == "child":
        q = q.filter_by(content_status="published")
    tasks = q.order_by(Task.id).all()
    return [_to_dict(t) for t in tasks]


@router.post("/generate")
def generate(user_id: int, d: date, force: bool = False,
             user: User = Depends(require_role("parent", "admin")),
             db: Session = Depends(get_db)):
    """手动生成当天任务。默认补缺失（幂等），force=true 覆盖重生成。"""
    ensure_user_access(user, user_id, db)
    generate_tasks_for_user(db, user_id, d, force=force)
    return {"ok": True}


@router.post("/approve-all")
def approve_all(req: ApproveAllReq, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    db.query(Task).filter_by(user_id=req.user_id, date=req.date, content_status="pending_review").update(
        {"content_status": "published"}, synchronize_session=False
    )
    db.commit()
    return {"ok": True}


@router.post("/{task_id}/approve")
def approve(task_id: int, user: User = Depends(require_role("parent", "admin")),
            db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    ensure_user_access(user, t.user_id, db)
    if t.content_status == "pending_review":
        t.content_status = "published"
        db.commit()
    return {"ok": True}


@router.put("/{task_id}")
def edit_task(task_id: int, req: EditReq, user: User = Depends(require_role("parent", "admin")),
              db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    ensure_user_access(user, t.user_id, db)
    if req.title:
        t.title = req.title
    if req.detail:
        t.detail = req.detail
    if req.content:
        t.content = req.content
    db.commit()
    return {"ok": True}


@router.delete("/{task_id}")
def delete_task(task_id: int, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    ensure_user_access(user, t.user_id, db)
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("")
def add_task(req: AddReq, user: User = Depends(require_role("parent", "admin")),
             db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    t = Task(
        user_id=req.user_id,
        date=req.date,
        subject=req.subject,
        task_type=req.task_type,
        title=req.title,
        detail=req.detail,
        content=req.content,
        points=req.points,
        content_status="published",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id}


@router.post("/{task_id}/submit")
def submit(task_id: int, user: User = Depends(require_learning_user),
           db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    ensure_user_access(user, t.user_id, db)
    if _dictation_photo_required(db, t):
        _raise_photo_required()
    _math_submit_blocked(db, t)
    if t.submit_status != "approved":
        t.submit_status = "submitted"
        db.commit()
    return {"ok": True}


@router.post("/{task_id}/knowledge-review")
def knowledge_review(task_id: int, req: KnowledgeReviewReq,
                     user: User = Depends(require_learning_user),
                     db: Session = Depends(get_db)):
    """基础知识任务：孩子逐题简答，混合判分，落知识点掌握度，然后提交待家长确认。"""
    from ..services.mastery import record_attempt
    from ..services.knowledge_quiz import grade_knowledge_answer
    from ..services.bucket_guard import resolve_bucket_id
    ensure_user_access(user, req.user_id, db)
    t = db.get(Task, task_id)
    if not t or t.task_type != "knowledge":
        return {"ok": False, "error": "任务不存在"}
    ensure_user_access(user, t.user_id, db)
    if t.submit_status == "approved":
        return {"ok": False, "error": "家长已确认，不能再修改"}
    try:
        points = json.loads(t.content or "[]")
    except ValueError:
        points = []
    bid = resolve_bucket_id(db, req.user_id, None)
    by_id = {p.get("id"): p for p in points}
    results = []
    for a in req.answers:
        p = by_id.get(a.get("id"))
        if p is None:
            continue
        user_answer = (a.get("user_answer") or "").strip()
        is_correct, _ = grade_knowledge_answer(
            user_answer, p.get("keywords") or [], p.get("answer") or "", db=db)
        if p.get("id"):
            record_attempt(db, req.user_id, "knowledge", p["id"], is_correct,
                           bucket_id=bid)
        p["last_correct"] = is_correct
        results.append({"id": p.get("id"), "is_correct": is_correct, "answer": p.get("answer") or ""})
    t.content = json.dumps(points, ensure_ascii=False)
    t.submit_status = "submitted"
    db.commit()
    correct = sum(1 for r in results if r["is_correct"])
    return {"ok": True, "results": results, "correct": correct, "total": len(results)}


@router.post("/{task_id}/upload-photo")
async def upload_photo(
    task_id: int,
    file: UploadFile = File(...),
    word_index: int | None = Form(None),
    user: User = Depends(require_learning_user),
    db: Session = Depends(get_db),
):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    ensure_user_access(user, t.user_id, db)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        return {"ok": False, "error": "unsupported file type"}
    data = await file.read()
    if len(data) > MAX_BYTES:
        return {"ok": False, "error": "file too large"}
    os.makedirs("uploads/task_photos", exist_ok=True)

    if t.task_type == "math" and word_index is not None:
        from ..services.math_gen import grade_math_work_photo, parse_math_task_content

        parsed = parse_math_task_content(t.content or "")
        words = parsed.get("word") or []
        if word_index < 0 or word_index >= len(words):
            return {"ok": False, "error": "invalid word_index"}
        path = f"uploads/task_photos/task_{task_id}_word_{word_index}{ext}"
        with open(path, "wb") as f:
            f.write(data)
        item = words[word_index]
        item["photo_path"] = path
        grade = grade_math_work_photo(
            db,
            data,
            item.get("question", ""),
            str(item.get("answer", "")),
        )
        item["ai_notes"] = grade.get("reason") or ""
        for k, v in grade.items():
            item[k] = v
        if not item.get("parent_status"):
            item["parent_status"] = "none"
        t.content = json.dumps(parsed, ensure_ascii=False)
        db.commit()
        return {"ok": True, "path": path, "word_index": word_index, "grade": grade}

    path = f"uploads/task_photos/task_{task_id}{ext}"
    with open(path, "wb") as f:
        f.write(data)
    t.photo_path = path
    db.commit()
    return {"ok": True, "path": path}


class RejectReq(BaseModel):
    scope: str = "task"


@router.post("/{task_id}/reject")
def reject_task(task_id: int, req: RejectReq | None = None,
                user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    """家长打回重做（MVP：整份 task）。"""
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    ensure_user_access(user, t.user_id, db)
    scope = (req.scope if req else "task") or "task"
    if scope != "task":
        return {"ok": False, "error": "unsupported scope"}
    if t.task_type == "math":
        from ..services.math_gen import parse_math_task_content

        parsed = parse_math_task_content(t.content or "")
        for c in parsed.get("calc") or []:
            c.pop("your_answer", None)
            c.pop("is_correct", None)
            c.pop("user_correct", None)
        for w in parsed.get("word") or []:
            w["parent_status"] = "rejected"
            w.pop("photo_path", None)
            for k in _PHOTO_AI_KEYS:
                w.pop(k, None)
        t.content = json.dumps(parsed, ensure_ascii=False)
    t.submit_status = "not_started"
    db.commit()
    return {"ok": True}


@router.post("/{task_id}/confirm")
def confirm(task_id: int, user: User = Depends(require_role("parent", "admin")),
            db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        return {"ok": False}
    ensure_user_access(user, t.user_id, db)
    if t.submit_status == "approved":
        return {"ok": True, "points": t.points, "already": True}
    if _dictation_photo_required(db, t):
        _raise_photo_required()
    if t.submit_status != "submitted":
        return {"ok": False, "error": "任务尚未提交，无法确认"}
    t.submit_status = "approved"
    db.add(Point(user_id=t.user_id, delta=t.points, reason=f"任务完成：{t.title}",
                 bucket_id=t.bucket_id))
    db.commit()
    return {"ok": True, "points": t.points}


class DrillStepReq(BaseModel):
    step: str = "recall"
    item_id: int
    answer: str = ""
    request_hint: bool = False


class DrillSentenceReq(BaseModel):
    item_id: int
    sentence: str = ""


class DrillCompleteReq(BaseModel):
    results: dict[str, bool] = {}


def _llm_judge_phrase(db, phrase: str, user_answer: str) -> bool:
    """LLM 兜底：判断孩子的回答是否「用对了这个短语」（不要求原样填回）。"""
    from ..services.ai import get_provider
    provider = get_provider(db)
    if provider.name == "fake":
        return False
    try:
        raw = provider.generate(
            prompt=(f"短语是「{phrase}」。孩子针对这道题的回答是「{user_answer}」。"
                    f"请判断孩子的回答是否正确使用了这个短语（允许 sb./sth. 被替换成具体的人/事，"
                    f"允许动词词形变化）。只返回 true 或 false。"),
            system="你是小学老师，判分。", json_mode=False)
        return raw.strip().lower().startswith("true")
    except Exception:
        return False


@router.post("/{task_id}/drill-step")
def drill_step(task_id: int, req: DrillStepReq, user: User = Depends(require_learning_user),
               db: Session = Depends(get_db)):
    from ..models import TrainingItem
    from ..services.grade_question import normalize_answer
    t = db.get(Task, task_id)
    if not t or t.task_type != "drill":
        return {"error": "not found"}
    content = json.loads(t.content or "{}")
    prog = content.get("progress", {})
    item = db.get(TrainingItem, req.item_id)
    expected = item.primary if item else ""
    correct = bool(expected) and normalize_answer(req.answer) == normalize_answer(expected)
    # 规则判错 → LLM 兜底：孩子是否「用对了短语」（如造了正确的句子）
    if not correct and expected and req.answer.strip():
        correct = _llm_judge_phrase(db, expected, req.answer)
    used = prog.get("hints_used", {}).get(str(req.item_id), 0)
    if correct:
        prog.setdefault("recall_results", {})[str(req.item_id)] = True
        hint = None
    else:
        used += 1
        prog["hints_used"] = prog.get("hints_used", {})
        prog["hints_used"][str(req.item_id)] = used
        prog.setdefault("recall_results", {})[str(req.item_id)] = False
        hint = f"提示 {used}/2" if used < 3 else None
    content["progress"] = prog
    t.content = json.dumps(content, ensure_ascii=False)
    db.commit()
    return {"correct": correct, "hints_remaining": max(0, 2 - used),
            "hint": hint, "reveal_answer": used >= 3,
            "expected": expected if not correct else None}


@router.post("/{task_id}/drill-sentence")
def drill_sentence(task_id: int, req: DrillSentenceReq, user: User = Depends(require_learning_user),
                   db: Session = Depends(get_db)):
    from ..models import TrainingItem
    t = db.get(Task, task_id)
    if not t or t.task_type != "drill":
        return {"error": "not found"}
    item = db.get(TrainingItem, req.item_id)
    phrase = item.primary if item else ""
    sent = req.sentence.strip()
    passed = bool(phrase and phrase.lower() in sent.lower() and len(sent) >= 4)
    return {"pass": passed, "feedback": "搭配正确。" if passed else "再试试，把短语用进完整句子里。"}


@router.post("/{task_id}/drill-apply")
def drill_apply(task_id: int, req: DrillSentenceReq, user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    from ..models import TrainingItem
    from ..services.grade_question import grade_subjective_with_ai
    item = db.get(TrainingItem, req.item_id)
    text = req.sentence.strip()
    if not text:
        return {"pass": False, "feedback": "写点什么吧。"}
    r = grade_subjective_with_ai(db, {"rubric": "用到了本组知识点、表达通顺", "sample": item.example or ""},
                                 {"text": text})
    if r["is_correct"] is True:
        return {"pass": True, "feedback": r.get("detail") or "写得好。"}
    if r["is_correct"] is False:
        return {"pass": False, "feedback": r.get("detail") or "再想想。"}
    kws = json.loads(item.keywords or "[]") if item else []
    if kws and any(k in text for k in kws):
        return {"pass": True, "feedback": "用到了关键内容。"}
    return {"pass": False, "feedback": "请家长/老师人工点评。"}


@router.post("/{task_id}/drill-complete")
def drill_complete(task_id: int, req: DrillCompleteReq, user: User = Depends(require_learning_user),
                   db: Session = Depends(get_db)):
    from ..models import TrainingItemMastery
    from ..services.drill_scheduler import grade
    from datetime import datetime, timedelta
    t = db.get(Task, task_id)
    if not t or t.task_type != "drill":
        return {"error": "not found"}
    content = json.loads(t.content or "{}")
    now = datetime.utcnow()
    hinted_any = wrong_any = False
    # 本次各条目的提示次数来自 content.progress.hints_used（drill-step 写入），
    # 而非 mastery 上持久化的 last_hinted（那是「上一次」的状态）。
    hints_used = (content.get("progress") or {}).get("hints_used", {})
    for item_id, is_correct in req.results.items():
        if not is_correct:
            wrong_any = True
        used_hint_this_time = (hints_used.get(str(item_id), 0) or 0) > 0
        m = db.query(TrainingItemMastery).filter_by(user_id=user.id, item_id=int(item_id)).first()
        if m is None:
            m = TrainingItemMastery(user_id=user.id, item_id=int(item_id), interval=1, lapse=0, last_hinted=False)
            db.add(m)
        ni, nl, nh = grade(m.interval, used_hint_this_time, is_correct, max_days=60)
        m.interval = ni; m.lapse += nl; m.last_hinted = nh
        m.attempts = json.dumps(json.loads(m.attempts or "[]") + [bool(is_correct)], ensure_ascii=False)
        m.next_review_at = now + timedelta(days=ni)
        if nh:
            hinted_any = True
    t.content = json.dumps(content, ensure_ascii=False)
    db.commit()
    stars = max(1, 3 - (1 if hinted_any else 0) - (1 if wrong_any else 0))
    return {"ok": True, "stars": stars, "review_due_tomorrow": 0}
