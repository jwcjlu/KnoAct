import os
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import PdfDocument, PdfPage, Lesson, WordBank, KnowledgePoint, Text
from ..services.pdf_split import render_pages, detect_lessons_from_pdf
from ..services.lesson_extract import extract_lesson_content

router = APIRouter(prefix="/api/pdf", tags=["pdf"])


@router.post("/upload")
async def upload_pdf(subject: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    path = f"uploads/{file.filename}"
    os.makedirs("uploads", exist_ok=True)
    with open(path, "wb") as f:
        f.write(await file.read())
    doc = PdfDocument(filename=file.filename, subject=subject, storage_path=path)
    db.add(doc); db.commit(); db.refresh(doc)

    pages = render_pages(doc.id, path, f"uploads/{doc.id}_pages")
    for p in pages:
        db.add(PdfPage(document_id=doc.id, page_number=p["page_number"], image_path=p["image_path"]))
    db.commit()

    # 自动拆课
    lessons = detect_lessons_from_pdf(path, subject)
    for l in lessons:
        db.add(Lesson(
            document_id=doc.id, subject=subject, title=l["title"],
            start_page=l["start_page"], end_page=l["end_page"],
            extract_status="pending", audit_status="pending",
        ))
    db.commit()
    return {"document_id": doc.id, "pages": len(pages), "lessons": len(lessons)}


@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(PdfDocument).all()
    out = []
    for d in docs:
        lessons = db.query(Lesson).filter_by(document_id=d.id).all()
        out.append({
            "id": d.id, "filename": d.filename, "subject": d.subject,
            "storage_path": d.storage_path,
            "lesson_count": len(lessons),
            "audited_count": sum(1 for l in lessons if l.audit_status == "approved"),
        })
    return out


@router.get("/documents/{document_id}/lessons")
def list_document_lessons(document_id: int, db: Session = Depends(get_db)):
    lessons = db.query(Lesson).filter_by(document_id=document_id).order_by(Lesson.start_page).all()
    out = []
    for l in lessons:
        words = [{"id": w.id, "word": w.word, "extra": w.extra} for w in db.query(WordBank).filter_by(lesson_id=l.id).all()]
        points = [{"id": p.id, "content": p.content, "category": p.category} for p in db.query(KnowledgePoint).filter_by(lesson_id=l.id).all()]
        texts = [t.content for t in db.query(Text).filter_by(lesson_id=l.id).all()]
        out.append({
            "id": l.id, "subject": l.subject, "title": l.title,
            "start_page": l.start_page, "end_page": l.end_page,
            "extract_status": l.extract_status, "audit_status": l.audit_status,
            "words": words, "points": points, "texts": texts,
        })
    return out


@router.post("/documents/{document_id}/extract")
def extract_document(document_id: int, db: Session = Depends(get_db)):
    """对文档下所有 pending 课程执行内容提取（生词/知识点/课文）。"""
    doc = db.get(PdfDocument, document_id)
    if not doc:
        return {"error": "not found"}
    lessons = db.query(Lesson).filter_by(document_id=document_id).all()
    extracted = 0
    for l in lessons:
        if l.extract_status == "done":
            continue
        content = extract_lesson_content(doc.storage_path, l.subject, l.start_page, l.end_page, db)
        for w in content["words"]:
            db.add(WordBank(lesson_id=l.id, subject=l.subject, word=w["word"], extra=w["extra"]))
        for p in content["points"]:
            db.add(KnowledgePoint(lesson_id=l.id, subject=l.subject, category="本课", content=p))
        if content["text"]:
            db.add(Text(lesson_id=l.id, content=content["text"]))
        l.extract_status = "done"
        extracted += 1
    db.commit()
    return {"extracted": extracted}


@router.post("/lessons/{lesson_id}/audit")
def audit_lesson(lesson_id: int, action: str = Form(...), db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        return {"error": "not found"}
    lesson.audit_status = "approved" if action == "通过" else "rejected"
    db.commit()
    return {"id": lesson.id, "audit_status": lesson.audit_status}
