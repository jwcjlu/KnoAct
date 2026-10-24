import os
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import PdfDocument, PdfPage, Lesson
from ..services.pdf_split import render_pages

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
    return {"document_id": doc.id, "pages": len(pages)}

@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    return db.query(PdfDocument).all()

@router.post("/lessons/{lesson_id}/audit")
def audit_lesson(lesson_id: int, action: str = Form(...), db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        return {"error": "not found"}
    lesson.audit_status = "approved" if action == "通过" else "rejected"
    db.commit()
    return {"id": lesson.id, "audit_status": lesson.audit_status}
