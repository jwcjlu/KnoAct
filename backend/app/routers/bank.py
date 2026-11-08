"""独立题库/卷：建卷、列卷、拉题、做题判分。"""
import json
import os
import re
from datetime import date as date_type

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.access import require_learning_user
from ..core.deps import get_current_user, require_role
from ..core.question_types import CATEGORY_OF_QTYPE
from ..core.source_adapter import QuestionDraft
from ..core.source_registry import SOURCE_REGISTRY
from ..services.source_config import tiku_cn_adapter, xuekubao_adapter
from ..database import get_db
from ..models import Mistake, Question, QuestionBank, ReadingPassage, User
from ..services.ai import ocr_image
from ..services.bucket_guard import resolve_bucket_id
from ..services.grade_question import grade_question, grade_subjective_with_ai
from ..services.ocr_import import structure_questions_from_text

_PHOTO_MAX_BYTES = 8 * 1024 * 1024
_PHOTO_MAX_PAGES = 8
_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_PHOTO_OCR_INSTRUCTION = (
    "识别试卷图片中的全部文字，保留题号、选项与表格。"
    "若是阅读理解，短文与题目都要原样输出，不要省略。"
)


def _photo_sort_key(name: str):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name or "")]


def _collect_photo_uploads(
    files: list[UploadFile] | None, file: UploadFile | None,
) -> list[UploadFile]:
    uploads: list[UploadFile] = []
    for f in files or []:
        if f is not None and (f.filename or "").strip():
            uploads.append(f)
    if file is not None and (file.filename or "").strip():
        uploads.append(file)
    uploads.sort(key=lambda f: _photo_sort_key(f.filename or ""))
    return uploads

router = APIRouter(prefix="/api/banks", tags=["bank"])


class BankCreateReq(BaseModel):
    title: str
    subject: str = ""
    grade: int | None = None
    tags: dict = {}
    source: str = "manual"


class BankSubmitReq(BaseModel):
    bank_id: int | None = None
    answers: list[dict]   # [{question_id, selected_index|blanks|pairs|text}]


class TikuSyncReq(BaseModel):
    keyword: str = ""
    subject: str = ""
    page: int = 1
    page_size: int = 20
    max_import: int = 20


class XuekubaoSyncReq(BaseModel):
    knowledge_id: str
    page: int = 1
    max_import: int = 20
    qtype_id: str | None = None
    diff: str | None = None
    year: int | None = None
    fetch_answers: bool = True


class ThirdPartyImportReq(BaseModel):
    source: str = "tiku.cn"
    items: list[dict] = []


def _require_bank(bank_id: int, user: User, db: Session) -> QuestionBank:
    bank = db.get(QuestionBank, bank_id)
    if not bank or (user.role != "admin" and bank.user_id != user.id):
        raise HTTPException(status_code=404, detail="卷子不存在")
    return bank


def _persist_drafts(db: Session, bank: QuestionBank, drafts: list[QuestionDraft], tag_source: str) -> list[int]:
    today = date_type.today()
    subj = (bank.subject or "").strip()
    ids: list[int] = []
    passages: dict[tuple[str, str], ReadingPassage] = {}
    for d in drafts:
        if not d.question:
            continue
        category = CATEGORY_OF_QTYPE.get(d.qtype, "subjective")
        tags = {**(d.tags or {}), "source": tag_source}
        passage_id = None
        content = (d.passage_content or "").strip()
        if content:
            raw_title = (d.passage_title or "").strip()
            key = (raw_title, content)
            psg = passages.get(key)
            if psg is None:
                psg = ReadingPassage(
                    user_id=bank.user_id,
                    bank_id=bank.id,
                    subject=subj,
                    title=raw_title or (bank.title or "").strip() or "阅读材料",
                    content=content,
                    grade=bank.grade,
                    status="pending",
                )
                db.add(psg)
                db.flush()
                passages[key] = psg
            passage_id = psg.id
        q = Question(
            bank_id=bank.id,
            qtype=d.qtype or "short_answer",
            qtype_category=category,
            question=d.question,
            answer=d.answer,
            answer_json=json.dumps(d.answer_json or {}, ensure_ascii=False),
            options=json.dumps(d.options or [], ensure_ascii=False),
            analysis=d.analysis or "",
            difficulty=d.difficulty or "medium",
            tags=json.dumps(tags, ensure_ascii=False),
            subject=subj,
            date=today,
            status="pending",
            passage_id=passage_id,
        )
        db.add(q)
        db.flush()
        ids.append(q.id)
    if ids and bank.source == "manual":
        bank.source = "third_party"
    return ids


@router.post("")
def create_bank(req: BankCreateReq, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    bank = QuestionBank(user_id=user.id, title=req.title.strip(), subject=req.subject,
                        grade=req.grade, tags=json.dumps(req.tags, ensure_ascii=False),
                        source=req.source)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return {"id": bank.id, "title": bank.title}


@router.get("")
def list_banks(user: User = Depends(require_role("parent", "admin")),
               db: Session = Depends(get_db)):
    banks = db.query(QuestionBank).filter_by(user_id=user.id).order_by(QuestionBank.id.desc()).all()
    q_counts = dict(
        db.query(Question.bank_id, func.count(Question.id))
        .filter(Question.bank_id.isnot(None))
        .group_by(Question.bank_id)
        .all()
    )
    out = []
    for b in banks:
        try:
            tags = json.loads(b.tags or "{}") if b.tags else {}
        except (ValueError, TypeError):
            tags = {}
        out.append({
            "id": b.id, "title": b.title, "subject": b.subject, "grade": b.grade,
            "source": b.source, "status": b.status,
            "question_count": int(q_counts.get(b.id, 0)),
            "include_daily_task": bool(tags.get("include_daily_task")),
        })
    return out


def _parent_id_for_practice(user: User) -> int | None:
    if user.role == "child":
        return user.parent_id
    if user.role in ("parent", "admin"):
        return user.id
    return None


@router.get("/practice")
def list_practice_banks(user: User = Depends(require_learning_user),
                        db: Session = Depends(get_db)):
    """孩子端练卷列表：绑定家长名下、含已发布题目的卷子。"""
    pid = _parent_id_for_practice(user)
    if pid is None:
        return []
    counts = dict(
        db.query(Question.bank_id, func.count(Question.id))
        .filter(Question.status == "published", Question.bank_id.isnot(None))
        .group_by(Question.bank_id)
        .all()
    )
    banks = (
        db.query(QuestionBank)
        .filter_by(user_id=pid, status="active")
        .order_by(QuestionBank.id.desc())
        .all()
    )
    return [
        {
            "id": b.id, "title": b.title, "subject": b.subject, "grade": b.grade,
            "question_count": int(counts.get(b.id, 0)),
        }
        for b in banks
        if counts.get(b.id, 0) > 0
    ]


def _format_student_answer(answer_row: dict, q: Question) -> str:
    if answer_row.get("text") is not None:
        return str(answer_row.get("text", ""))
    if answer_row.get("blanks") is not None:
        return "；".join(str(x) for x in (answer_row.get("blanks") or []))
    if answer_row.get("pairs") is not None:
        return json.dumps(answer_row.get("pairs"), ensure_ascii=False)
    sel = answer_row.get("selected_index")
    if sel is not None:
        opts = json.loads(q.options or "[]")
        if isinstance(sel, list):
            labels = []
            for i in sel:
                if isinstance(i, int) and 0 <= i < len(opts):
                    labels.append(str(opts[i].get("label", i)))
            return "、".join(labels) if labels else json.dumps(sel, ensure_ascii=False)
        if isinstance(sel, int) and 0 <= sel < len(opts):
            return str(opts[sel].get("label", sel))
        return str(sel)
    return ""


@router.get("/{bank_id}/questions")
def list_bank_questions(
    bank_id: int,
    ids: str = "",
    _auth: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Question).filter_by(bank_id=bank_id, status="published")
    if ids.strip():
        qids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if qids:
            q = q.filter(Question.id.in_(qids))
    qs = q.order_by(Question.id).all()
    pids = {x.passage_id for x in qs if x.passage_id}
    passages = {}
    if pids:
        for p in db.query(ReadingPassage).filter(ReadingPassage.id.in_(pids)).all():
            passages[p.id] = {"id": p.id, "title": p.title, "content": p.content, "subject": p.subject}
    return [{
        "id": item.id, "qtype": item.qtype, "qtype_category": item.qtype_category,
        "question": item.question, "options": json.loads(item.options or "[]"),
        "answer": item.answer, "analysis": item.analysis, "difficulty": item.difficulty,
        "tags": json.loads(item.tags or "{}"),
        "passage_id": item.passage_id,
        "passage": passages.get(item.passage_id),
    } for item in qs]


@router.post("/submit")
def submit_bank(req: BankSubmitReq, user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    qids = [a.get("question_id") for a in req.answers]
    # 只判已发布的题，且给定 bank_id 时限定在该卷内；杜绝越权给草稿/他卷题目判分泄答案
    q = db.query(Question).filter(Question.id.in_(qids), Question.status == "published")
    if req.bank_id is not None:
        q = q.filter(Question.bank_id == req.bank_id)
    qs = q.all()
    by_id = {x.id: x for x in qs}
    results = []
    for a in req.answers:
        qid = a.get("question_id")
        qq = by_id.get(qid)
        if qq is None:
            results.append({"question_id": qid, "is_correct": False})
            continue
        answer_json = json.loads(qq.answer_json or "{}")
        student = {k: a.get(k) for k in ("selected_index", "blanks", "pairs", "text") if a.get(k) is not None}
        if qq.qtype_category == "subjective":
            r = grade_subjective_with_ai(db, answer_json, student)
        else:
            r = grade_question(qq.qtype_category, answer_json, student)
        results.append({"question_id": qq.id, "is_correct": r["is_correct"],
                        "correct_answer_text": r["correct_answer_text"], "detail": r["detail"]})
        if r["is_correct"] is False:
            bid = resolve_bucket_id(db, user.id, None)
            db.add(Mistake(
                user_id=user.id,
                source_type="bank",
                question=qq.question,
                your_answer=_format_student_answer(a, qq),
                correct_answer=r.get("correct_answer_text") or qq.answer,
                bucket_id=bid,
            ))
    score = sum(1 for r in results if r["is_correct"] is True)
    db.commit()
    return {"answers": results, "score": score, "total": len(results)}


@router.post("/{bank_id}/photo-import")
async def photo_import_bank(
    bank_id: int,
    files: list[UploadFile] | None = File(None),
    file: UploadFile | None = File(None),
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """卷子拍照（可多页）→ OCR 按文件名顺序拼接 → LLM 结构化 → 待审核入库。"""
    bank = _require_bank(bank_id, user, db)
    uploads = _collect_photo_uploads(files, file)
    if not uploads:
        raise HTTPException(status_code=400, detail="请上传图片")
    if len(uploads) > _PHOTO_MAX_PAGES:
        raise HTTPException(status_code=400, detail=f"一次最多 {_PHOTO_MAX_PAGES} 张")
    pages: list[str] = []
    for i, up in enumerate(uploads, 1):
        ext = os.path.splitext(up.filename or "")[1].lower()
        if ext not in _PHOTO_EXT:
            raise HTTPException(status_code=400, detail="不支持的图片格式")
        data = await up.read()
        if len(data) > _PHOTO_MAX_BYTES:
            raise HTTPException(status_code=400, detail="图片过大")
        try:
            text = ocr_image(db, data, instruction=_PHOTO_OCR_INSTRUCTION)
        except Exception:
            text = ""
        text = (text or "").strip()
        if text:
            pages.append(f"【第{i}页】\n{text}")
    ocr_text = "\n\n".join(pages)
    drafts = structure_questions_from_text(db, ocr_text or "")
    if not drafts:
        return {"count": 0, "ids": [], "message": "未能识别题目，请换更清晰照片或改用手工录入"}
    ids = _persist_drafts(db, bank, drafts, "photo")
    if ids and bank.source != "third_party":
        bank.source = "photo"
    db.commit()
    return {"count": len(ids), "ids": ids}


@router.post("/{bank_id}/sync-tiku")
def sync_tiku_bank(
    bank_id: int,
    req: TikuSyncReq,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """从 tiku.cn B2B API 拉题并写入待审核队列（需环境变量配置）。"""
    bank = _require_bank(bank_id, user, db)
    adapter = tiku_cn_adapter(db)
    if not adapter.configured():
        raise HTTPException(
            status_code=503,
            detail="tiku.cn API 未配置：请在「设置 → 题库来源」填写，或设置环境变量 TIKU_CN_API_BASE / TIKU_CN_APP_KEY",
        )
    subject = (req.subject or bank.subject or "").strip()
    raw = adapter.fetch(
        keyword=req.keyword.strip(),
        subject=subject,
        page=req.page,
        page_size=req.page_size,
        grade=bank.grade,
    )
    if raw.get("error") and not _extract_items_safe(raw):
        raise HTTPException(
            status_code=502,
            detail=raw.get("message") or raw.get("error") or "拉取失败",
        )
    drafts = adapter.normalize(raw)[: max(1, min(req.max_import, 50))]
    if not drafts:
        return {"count": 0, "ids": [], "message": "未解析到题目，请核对 API 响应格式或改用 import-third-party"}
    ids = _persist_drafts(db, bank, drafts, "tiku.cn")
    db.commit()
    return {"count": len(ids), "ids": ids}


@router.post("/{bank_id}/sync-xuekubao")
def sync_xuekubao_bank(
    bank_id: int,
    req: XuekubaoSyncReq,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """按学库宝知识点 knowledgeId（章节树三级 oldId）拉题并写入待审核队列。"""
    bank = _require_bank(bank_id, user, db)
    adapter = xuekubao_adapter(db)
    if not adapter.configured():
        raise HTTPException(
            status_code=503,
            detail="学库宝 API 未配置：请在「设置 → 题库来源」填写 Access Key，或设置环境变量 XUEKUBAO_ACCESS_KEY",
        )
    raw = adapter.fetch_by_knowledge(
        knowledge_id=req.knowledge_id.strip(),
        page=req.page,
        qtype_id=req.qtype_id,
        diff=req.diff,
        year=req.year,
        fetch_answers=req.fetch_answers,
    )
    items = raw.get("data") if isinstance(raw.get("data"), list) else _extract_items_safe(raw)
    err = str(raw.get("errorCode") or "")
    if not items and err not in ("0", "200", ""):
        raise HTTPException(
            status_code=502,
            detail=raw.get("message") or raw.get("errorCode") or "拉取失败",
        )
    drafts = adapter.normalize(raw)[: max(1, min(req.max_import, 50))]
    if not drafts:
        return {
            "count": 0,
            "ids": [],
            "message": "未解析到题目，请核对 knowledge_id 或改用 import-third-party",
            "data_count": raw.get("dataCount"),
        }
    ids = _persist_drafts(db, bank, drafts, "xuekubao")
    db.commit()
    return {"count": len(ids), "ids": ids, "data_count": raw.get("dataCount")}


def _extract_items_safe(raw) -> list:
    from ..core.tiku_cn_adapter import _extract_items
    return _extract_items(raw)


@router.post("/{bank_id}/import-third-party")
def import_third_party(
    bank_id: int,
    req: ThirdPartyImportReq,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """无需在线 API：将第三方已拉取的题目 JSON 标准化入库（source 须在 SOURCE_REGISTRY）。"""
    bank = _require_bank(bank_id, user, db)
    adapter = SOURCE_REGISTRY.get(req.source)
    if adapter is None:
        raise HTTPException(status_code=400, detail=f"未知来源 {req.source}")
    drafts = adapter.normalize({"list": req.items})
    if not drafts:
        raise HTTPException(status_code=400, detail="无法解析题目列表")
    ids = _persist_drafts(db, bank, drafts, req.source)
    db.commit()
    return {"count": len(ids), "ids": ids}
