import os
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
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
from ..models import PdfDocument, PdfPage, Lesson, WordBank, KnowledgePoint, Text, Question, Textbook, UserDocument
from ..services.cleanup import purge_lesson_content, purge_lessons
from ..services.pdf_split import render_pages, detect_lessons_from_pdf
from ..services.lesson_extract import extract_lesson_content
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
                   user: User = Depends(require_learning_user),
                   db: Session = Depends(get_db)):
    """列出教材：家长/管理员可查全库或按 user_id 过滤已绑定；孩子仅能看到本人已绑定的文档。"""
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
        words = [{"id": w.id, "word": w.word, "extra": w.extra} for w in db.query(WordBank).filter_by(lesson_id=l.id).all()]
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
                content = extract_lesson_content(storage_path, t["subject"], t["start_page"], t["end_page"], db)
                # 清除本课旧数据后写入新结果
                purge_lesson_content(db, [t["id"]])
                for w in content["words"]:
                    db.add(WordBank(lesson_id=t["id"], subject=t["subject"], word=w["word"], extra=w["extra"]))
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
        prog["done"] = len(tasks)
        prog["finished"] = True
    except Exception as e:
        prog["error"] = str(e)[:300]
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
    lesson.audit_status = "approved" if action == "通过" else "rejected"
    db.commit()
    return {"id": lesson.id, "audit_status": lesson.audit_status}


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

    # 清理关联表
    purge_lessons(db, lesson_ids)
    db.query(PdfPage).filter_by(document_id=document_id).delete(synchronize_session=False)
    db.query(Textbook).filter_by(document_id=document_id).delete(synchronize_session=False)
    db.query(UserDocument).filter_by(document_id=document_id).delete(synchronize_session=False)

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
    return {"ok": True, "deleted": document_id}
