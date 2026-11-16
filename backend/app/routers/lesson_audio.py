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
