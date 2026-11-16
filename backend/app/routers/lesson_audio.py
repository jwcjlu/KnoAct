"""教材配套真人音频：上传/列表/改绑定/时间点标记。"""
import json
import os
import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import ensure_pdf_document_access
from ..core.deps import require_role
from ..database import get_db
from ..models import Lesson, LessonAudio, User

router = APIRouter(prefix="/api/lesson-audio", tags=["lesson-audio"])

_UNIT_RE = re.compile(r"^(?:\d+_)?Unit\s*(\d+)", re.IGNORECASE)


def parse_unit_label(filename: str) -> str:
    """从文件名解析展示名：Unit N / Word list；解析不出则回落到去扩展名的原名。"""
    base = os.path.splitext(os.path.basename(filename))[0]
    m = _UNIT_RE.match(base)
    if m:
        return f"Unit {int(m.group(1))}"
    if "word" in base.lower() and "list" in base.lower():
        return "Word list"
    return base


def _match_lesson_by_label(db: Session, document_id: int, subject: str, label: str) -> Lesson | None:
    """按 label（如 Unit 1）匹配教材下同一学科的课；0 或多个匹配均返回 None。"""
    if label == "Word list":
        return None
    q = db.query(Lesson).filter_by(document_id=document_id, subject=subject)
    hits = [l for l in q.all() if label in (l.title or "")]
    return hits[0] if len(hits) == 1 else None


@router.post("")
def upload_audio(
    file: UploadFile = File(...),
    document_id: int = Form(...),
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    doc = ensure_pdf_document_access(user, document_id, db)
    if not (file.filename or "").lower().endswith(".mp3"):
        raise HTTPException(status_code=400, detail="仅支持 MP3 音频")
    os.makedirs("uploads/audio", exist_ok=True)
    label = parse_unit_label(file.filename)
    safe = os.path.basename(file.filename or "audio.mp3")
    path = f"uploads/audio/{document_id}_{safe}"
    with open(path, "wb") as f:
        f.write(file.file.read())
    lesson = _match_lesson_by_label(db, document_id, doc.subject, label)
    row = LessonAudio(
        lesson_id=lesson.id if lesson else None,
        document_id=document_id,
        unit_label=label,
        audio_path=path,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "lesson_id": row.lesson_id, "unit_label": row.unit_label,
            "audio_path": row.audio_path, "marks": json.loads(row.marks_json)}
