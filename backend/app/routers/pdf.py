import os
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..core.access import (
    ensure_pdf_document_access,
    ensure_user_access,
    require_learning_user,
    resolve_target_user_id,
)
from ..core.deps import get_current_user, require_role
from ..database import get_db, SessionLocal
from ..models import User
from ..models import PdfDocument, PdfPage, Lesson, LessonAudio, WordBank, KnowledgePoint, Text, Question, Textbook, UserDocument
from ..services.cleanup import detach_points, detach_words, purge_lesson_content, purge_lessons
from ..services.pdf_split import render_pages, detect_lessons_from_pdf
from ..services.lesson_extract import (
    apply_chinese_word_tables,
    apply_word_list,
    extract_lesson_content,
    _replace_lesson_words,
    _kind_key,
)
from ..services.word_kinds import normalize_kind, KIND_WORD
from ..services.question_gen import generate_reading_questions

router = APIRouter(prefix="/api/pdf", tags=["pdf"])

# 提取进度：{document_id: {"total": int, "done": int, "current": str, "finished": bool}}
_EXTRACT_PROGRESS = {}


@router.post("/upload")
async def upload_pdf(subject: str = Form(...), grade: int = Form(None),
                     edition: str = Form(""), content_kind: str = Form("textbook"),
                     handout_kind: str = Form(None), file: UploadFile = File(...),
                     _auth: User = Depends(require_role("parent", "admin")),
                     db: Session = Depends(get_db)):
    os.makedirs("uploads", exist_ok=True)

    # 先建文档记录拿到 id，用「id + 原文件名」生成唯一存储路径，避免重名文件互相覆盖/共用
    doc = PdfDocument(filename=file.filename, subject=subject, storage_path="",
                      grade=grade, edition=edition,
                      content_kind=content_kind, handout_kind=handout_kind or None)
    db.add(doc); db.commit(); db.refresh(doc)

    safe_name = os.path.basename(file.filename or "upload.pdf")
    path = f"uploads/{doc.id}_{safe_name}"
    with open(path, "wb") as f:
        f.write(await file.read())
    doc.storage_path = path
    db.commit()

    pages = render_pages(doc.id, path, f"uploads/{doc.id}_pages")
    for p in pages:
        db.add(PdfPage(document_id=doc.id, page_number=p["page_number"], image_path=p["image_path"]))
    db.commit()

    if content_kind == "handout":
        # 讲义：跳过自动拆课，不建 Lesson
        return {"document_id": doc.id, "pages": len(pages), "lessons": 0}

    # 自动拆课
    lessons = detect_lessons_from_pdf(path, subject, db)
    for l in lessons:
        db.add(Lesson(
            document_id=doc.id, subject=subject, title=l["title"],
            start_page=l["start_page"], end_page=l["end_page"],
            extract_status="pending", audit_status="pending",
        ))
    db.commit()
    return {"document_id": doc.id, "pages": len(pages), "lessons": len(lessons)}


@router.get("/documents")
def list_documents(user_id: int | None = None,
                   include_practice: bool = False,
                   user: User = Depends(require_learning_user),
                   db: Session = Depends(get_db)):
    """列出教材：家长/管理员可查全库或按 user_id 过滤已绑定；孩子仅能看到本人已绑定的文档。

    `include_practice=false`（默认）时排除练习册导入的 PDF —— 它们只在
    「题库管理 → 练习册导入」里出现，不应混进教材列表。
    """
    if user.role == "child":
        effective_user_id = user.id
    elif user_id is not None:
        ensure_user_access(user, user_id, db)
        effective_user_id = user_id
    else:
        effective_user_id = None

    q = db.query(PdfDocument)
    if effective_user_id is not None:
        bound = db.query(UserDocument.document_id).filter_by(user_id=effective_user_id)
        q = q.filter(PdfDocument.id.in_(bound))
    if not include_practice:
        # 练习册（content_kind='practice'）不进教材列表；NULL 视为教材
        q = q.filter(
            or_(PdfDocument.content_kind.is_(None),
                PdfDocument.content_kind != "practice")
        )
    docs = q.all()
    out = []
    for d in docs:
        lessons = db.query(Lesson).filter_by(document_id=d.id).all()
        out.append({
            "id": d.id, "filename": d.filename, "subject": d.subject,
            "storage_path": d.storage_path,
            "grade": d.grade, "edition": d.edition,
            "lesson_count": len(lessons),
            "audited_count": sum(1 for l in lessons if l.audit_status == "approved"),
        })
    return out


@router.get("/documents/{document_id}/lessons")
def list_document_lessons(document_id: int, user: User = Depends(require_learning_user),
                          db: Session = Depends(get_db)):
    doc = ensure_pdf_document_access(user, document_id, db)
    # 页图缓存版本：document 创建时间戳（毫秒），前端拼 ?v= 使教材重渲染后缓存自然失效
    doc_version = int(doc.created_at.timestamp() * 1000) if doc.created_at else 0
    lessons = db.query(Lesson).filter_by(document_id=document_id).order_by(Lesson.start_page).all()
    out = []
    for l in lessons:
        words = [
            {"id": w.id, "word": w.word, "extra": w.extra, "kind": w.kind}
            for w in db.query(WordBank).filter_by(lesson_id=l.id).all()
        ]
        points = [{"id": p.id, "content": p.content, "category": p.category} for p in db.query(KnowledgePoint).filter_by(lesson_id=l.id).all()]
        texts = [t.content for t in db.query(Text).filter_by(lesson_id=l.id).all()]
        pages = db.query(PdfPage).filter(
            PdfPage.document_id == document_id,
            PdfPage.page_number >= l.start_page,
            PdfPage.page_number <= l.end_page,
        ).order_by(PdfPage.page_number).all()
        out.append({
            "id": l.id, "subject": l.subject, "title": l.title,
            "start_page": l.start_page, "end_page": l.end_page,
            "extract_status": l.extract_status, "audit_status": l.audit_status,
            "words": words, "points": points, "texts": texts,
            "pages": [{"page_number": p.page_number, "image_path": p.image_path} for p in pages],
            "document_version": doc_version,
        })
    return out


class BindReq(BaseModel):
    user_id: int


class LessonWordIn(BaseModel):
    id: int | None = None
    word: str = ""
    extra: str = ""
    kind: str | None = None


class LessonPointIn(BaseModel):
    id: int | None = None
    content: str = ""
    category: str = "本课"


class LessonContentIn(BaseModel):
    title: str
    words: list[LessonWordIn] = []
    points: list[LessonPointIn] = []


@router.post("/documents/{document_id}/bind")
def bind_document(document_id: int, req: BindReq, user: User = Depends(require_role("parent", "admin")),
                  db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    exists = db.query(UserDocument).filter_by(user_id=req.user_id, document_id=document_id).first()
    if not exists:
        db.add(UserDocument(user_id=req.user_id, document_id=document_id))
        db.commit()
    return {"ok": True}


@router.delete("/documents/{document_id}/bind")
def unbind_document(document_id: int, user_id: int, user: User = Depends(require_role("parent", "admin")),
                    db: Session = Depends(get_db)):
    ensure_user_access(user, user_id, db)
    db.query(UserDocument).filter_by(user_id=user_id, document_id=document_id).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.get("/documents/{document_id}/bound-users")
def bound_users(document_id: int, _auth: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    ids = [r[0] for r in db.query(UserDocument.user_id).filter_by(document_id=document_id).all()]
    return {"user_ids": ids}


@router.post("/documents/{document_id}/extract")
def extract_document(document_id: int, background_tasks: BackgroundTasks,
                     _auth: User = Depends(require_role("parent", "admin")),
                     db: Session = Depends(get_db)):
    """对文档下所有 pending 课程执行内容提取（生词/知识点/课文）。

    提取走后台任务（每课一次 AI 调用，25 课约 10~15 分钟），本接口立即返回；
    前端轮询 GET /documents/{id}/extract/progress 查看进度。
    """
    doc = db.get(PdfDocument, document_id)
    if not doc:
        return {"error": "not found"}
    if not os.path.exists(doc.storage_path):
        return {"error": "源文件不存在"}

    pending = db.query(Lesson).filter_by(document_id=document_id).all()
    pending = [l for l in pending if l.extract_status != "done"]
    if not pending:
        # 课已经提过，但扫描版单词表此前没解析进各课。英语教材再走一遍书末 Word list。
        if doc.subject == "英语":
            _EXTRACT_PROGRESS[document_id] = {
                "total": 1, "done": 0, "current": "Word list",
                "finished": False, "error": "",
            }
            background_tasks.add_task(_run_word_list_sync, document_id, doc.storage_path)
            return {"started": True, "total": 1, "word_list": True}
        # 语文课都已提取过时，再走一遍册末识字表/写字表/词语表回填。
        if doc.subject == "语文":
            _EXTRACT_PROGRESS[document_id] = {
                "total": 1, "done": 0, "current": "册末字词表",
                "finished": False, "error": "",
            }
            background_tasks.add_task(_run_chinese_word_tables_sync, document_id, doc.storage_path)
            return {"started": True, "total": 1, "chinese_word_tables": True}
        return {"extracted": 0, "message": "无可提取课程"}

    _EXTRACT_PROGRESS[document_id] = {
        "total": len(pending), "done": 0, "current": pending[0].title,
        "finished": False, "error": "",
    }
    # 记录课程 id、页码、学科、存储路径，供后台任务按 id 重新加载（避免跨线程共享 session）
    tasks = [{"id": l.id, "title": l.title, "start_page": l.start_page,
              "end_page": l.end_page, "subject": l.subject} for l in pending]
    background_tasks.add_task(_run_extract, document_id, doc.storage_path, tasks)
    return {"started": True, "total": len(pending)}


def _run_extract(document_id: int, storage_path: str, tasks: list[dict]):
    """后台逐课提取。每课独立 session，避免线程安全问题。"""
    prog = _EXTRACT_PROGRESS.get(document_id, {})
    try:
        for i, t in enumerate(tasks):
            prog["done"] = i
            prog["current"] = t["title"]
            db = SessionLocal()
            try:
                lesson = db.get(Lesson, t["id"])
                if lesson is None:
                    continue
                doc = db.get(PdfDocument, document_id)
                grade = doc.grade if doc is not None else None
                content = extract_lesson_content(
                    storage_path, t["subject"], t["start_page"], t["end_page"], db, grade=grade,
                )
                lesson_id = t["id"]
                point_ids = [r[0] for r in db.query(KnowledgePoint.id).filter_by(lesson_id=lesson_id).all()]
                detach_points(db, point_ids)
                db.query(KnowledgePoint).filter_by(lesson_id=lesson_id).delete(synchronize_session=False)
                db.query(Text).filter_by(lesson_id=lesson_id).delete(synchronize_session=False)
                db.query(Question).filter_by(lesson_id=lesson_id).delete(synchronize_session=False)
                _replace_lesson_words(db, lesson, content.get("words") or [])
                for p in content["points"]:
                    db.add(KnowledgePoint(lesson_id=t["id"], subject=t["subject"], category="本课", content=p))
                if content["text"]:
                    db.add(Text(lesson_id=t["id"], content=content["text"]))
                    for q in generate_reading_questions(db, content["text"], n=3):
                        db.add(Question(lesson_id=t["id"], qtype="reading", question=q["question"], answer=q["answer"]))
                lesson.extract_status = "done"
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        if any(t.get("subject") == "英语" for t in tasks):
            prog["current"] = "Word list"
            _sync_word_list(document_id, storage_path, prog)
        if any(t.get("subject") == "语文" for t in tasks):
            prog["current"] = "册末字词表"
            _sync_chinese_word_tables(document_id, storage_path, prog)
        prog["done"] = len(tasks)
        prog["finished"] = True
    except Exception as e:
        prog["error"] = str(e)[:300]
        prog["finished"] = True


def _sync_word_list(document_id: int, storage_path: str, prog: dict) -> None:
    db = SessionLocal()
    try:
        apply_word_list(db, document_id, storage_path)
    except Exception as e:
        prog["error"] = str(e)[:300]
    finally:
        db.close()


def _run_word_list_sync(document_id: int, storage_path: str):
    """各课已提取完成时，只重解析书末 Word list 并写回生词表。"""
    prog = _EXTRACT_PROGRESS.get(document_id, {})
    try:
        _sync_word_list(document_id, storage_path, prog)
        prog["done"] = 1
    finally:
        prog["finished"] = True


def _sync_chinese_word_tables(document_id: int, storage_path: str, prog: dict) -> None:
    db = SessionLocal()
    try:
        apply_chinese_word_tables(db, document_id, storage_path)
    except Exception as e:
        prog["error"] = str(e)[:300]
    finally:
        db.close()


def _run_chinese_word_tables_sync(document_id: int, storage_path: str):
    """各课已提取完成时，只重解析册末字词表并写回生词表。"""
    prog = _EXTRACT_PROGRESS.get(document_id, {})
    try:
        _sync_chinese_word_tables(document_id, storage_path, prog)
        prog["done"] = 1
    finally:
        prog["finished"] = True


@router.get("/documents/{document_id}/extract/progress")
def extract_progress(document_id: int, _auth: User = Depends(require_role("parent", "admin"))):
    prog = _EXTRACT_PROGRESS.get(document_id)
    if not prog:
        return {"finished": True, "done": 0, "total": 0}
    return prog


@router.post("/lessons/{lesson_id}/audit")
def audit_lesson(lesson_id: int, action: str = Form(...),
                  _auth: User = Depends(require_role("parent", "admin")),
                  db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        return {"error": "not found"}
    if action == "通过":
        lesson.audit_status = "approved"
    elif action == "撤回":
        lesson.audit_status = "pending"
    else:
        lesson.audit_status = "rejected"
    db.commit()
    return {"id": lesson.id, "audit_status": lesson.audit_status}


@router.put("/lessons/{lesson_id}/content")
def update_lesson_content(lesson_id: int, req: LessonContentIn,
                           _auth: User = Depends(require_role("parent", "admin")),
                           db: Session = Depends(get_db)):
    """家长改一课的课名、生词（含释义）和知识点。已有词按 id 原地更新，听写记录跟着走；删掉的词清掉掌握记录。"""
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        return {"error": "not found"}
    title = (req.title or "").strip()
    if not title:
        return {"error": "课名不能为空"}
    if len(title) > 255:
        return {"error": "课名过长"}

    subject = lesson.subject or ""
    words = []
    for w in req.words:
        word = (w.word or "").strip()
        if not word:
            continue
        if len(word) > 64:
            return {"error": "生词不能超过 64 个字符"}
        raw_kind = (w.kind or "").strip()
        if subject == "语文":
            if not raw_kind:
                return {"error": "语文生词必须指定 kind"}
            try:
                kind = normalize_kind(raw_kind)
            except ValueError:
                return {"error": f"无效的生词类型: {raw_kind}"}
        else:
            if not raw_kind:
                kind = KIND_WORD
            else:
                try:
                    kind = normalize_kind(raw_kind)
                except ValueError:
                    return {"error": f"无效的生词类型: {raw_kind}"}
        words.append((w.id, word, (w.extra or "").strip(), kind))
    points = []
    for p in req.points:
        content = (p.content or "").strip()
        if not content:
            continue
        category = ((p.category or "本课").strip() or "本课")[:32]
        points.append((p.id, content, category))

    lesson.title = title
    existing_words = {w.id: w for w in db.query(WordBank).filter_by(lesson_id=lesson.id).all()}
    kept_words: set[int] = set()
    for wid, word, extra, kind in words:
        row = existing_words.get(wid) if wid else None
        if row is not None and _kind_key(row.kind or "", subject) == _kind_key(kind, subject):
            row.word = word
            row.extra = extra
            row.kind = kind
            kept_words.add(row.id)
        else:
            db.add(WordBank(
                lesson_id=lesson.id, subject=lesson.subject,
                word=word, extra=extra, kind=kind,
            ))
    drop_words = [i for i in existing_words if i not in kept_words]
    for i in drop_words:
        db.expunge(existing_words[i])
    detach_words(db, drop_words)
    if drop_words:
        db.query(WordBank).filter(WordBank.id.in_(drop_words)).delete(synchronize_session=False)

    existing_points = {p.id: p for p in db.query(KnowledgePoint).filter_by(lesson_id=lesson.id).all()}
    kept_points: set[int] = set()
    for pid, content, category in points:
        row = existing_points.get(pid) if pid else None
        if row is None:
            db.add(KnowledgePoint(lesson_id=lesson.id, subject=lesson.subject, category=category, content=content))
        else:
            row.content = content
            row.category = category
            kept_points.add(row.id)
    drop_points = [i for i in existing_points if i not in kept_points]
    for i in drop_points:
        db.expunge(existing_points[i])
    detach_points(db, drop_points)
    if drop_points:
        db.query(KnowledgePoint).filter(KnowledgePoint.id.in_(drop_points)).delete(synchronize_session=False)

    db.commit()
    return {"ok": True, "id": lesson.id, "title": lesson.title}


@router.post("/documents/{document_id}/resplit")
def resplit_document(document_id: int, _auth: User = Depends(require_role("parent", "admin")),
                     db: Session = Depends(get_db)):
    """重新拆分教材：删除该文档下的旧课程（连同其生词/知识点/课文/掌握记录），
    按锚点重新切分，生成新的待审核课程。"""
    doc = db.get(PdfDocument, document_id)
    if not doc:
        return {"error": "not found"}
    if not os.path.exists(doc.storage_path):
        return {"error": "源文件不存在"}

    old_ids = [r[0] for r in db.query(Lesson.id).filter_by(document_id=document_id).all()]
    # 无外键级联：手动清理课程及引用它的行
    purge_lessons(db, old_ids)
    db.flush()

    lessons = detect_lessons_from_pdf(doc.storage_path, doc.subject, db)
    for l in lessons:
        db.add(Lesson(
            document_id=doc.id, subject=doc.subject, title=l["title"],
            start_page=l["start_page"], end_page=l["end_page"],
            extract_status="pending", audit_status="pending",
        ))
    db.commit()
    return {"lessons": len(lessons)}


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, _auth: User = Depends(require_role("parent", "admin")),
                    db: Session = Depends(get_db)):
    """移除教材：删除文档、页面、课程及其生词/知识点/课文/掌握记录，并清理磁盘文件。"""
    doc = db.get(PdfDocument, document_id)
    if not doc:
        return {"error": "not found"}

    lesson_ids = [r[0] for r in db.query(Lesson.id).filter_by(document_id=document_id).all()]

    # 清理关联表。音频文件挂在教材上，移除教材时一并删掉
    audio_paths = [r[0] for r in db.query(LessonAudio.audio_path).filter_by(document_id=document_id).all()]
    purge_lessons(db, lesson_ids)
    db.query(LessonAudio).filter_by(document_id=document_id).delete(synchronize_session=False)
    db.query(PdfPage).filter_by(document_id=document_id).delete(synchronize_session=False)
    db.query(Textbook).filter_by(document_id=document_id).delete(synchronize_session=False)
    db.query(UserDocument).filter_by(document_id=document_id).delete(synchronize_session=False)

    # 练习册导入产物无外键级联，必须显式清理
    from ..models import (
        PracticeImportJob, PracticeImportPage, PracticeQuestionGroup, Question,
    )

    gids = [g.id for g in db.query(PracticeQuestionGroup)
            .filter_by(source_document_id=document_id).all()]
    if gids:
        db.query(Question).filter(Question.group_id.in_(gids)).delete(
            synchronize_session=False)
        db.query(PracticeQuestionGroup).filter(
            PracticeQuestionGroup.id.in_(gids)).delete(synchronize_session=False)
    db.query(PracticeImportPage).filter_by(document_id=document_id).delete(
        synchronize_session=False)
    db.query(Question).filter(Question.source_document_id == document_id).delete(
        synchronize_session=False)
    # 导入任务行也是无 ondelete 的裸外键；MySQL 上不清它会撞 FK 约束
    db.query(PracticeImportJob).filter_by(document_id=document_id).delete(
        synchronize_session=False)
    db.flush()

    # 记录磁盘文件路径，用于删除
    storage = doc.storage_path
    page_dir = f"uploads/{doc.id}_pages"

    db.delete(doc)
    db.commit()

    # 清理磁盘：仅当没有其他文档仍引用该存储路径时才删除文件（防重名共用误删）
    try:
        if storage and os.path.exists(storage):
            still_used = db.query(PdfDocument).filter(
                PdfDocument.storage_path == storage, PdfDocument.id != document_id
            ).first()
            if not still_used:
                os.remove(storage)
    except OSError:
        pass
    try:
        if os.path.isdir(page_dir):
            import shutil
            shutil.rmtree(page_dir, ignore_errors=True)
    except OSError:
        pass
    for path in audio_paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    return {"ok": True, "deleted": document_id}
