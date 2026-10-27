# backend/tests/test_render_task.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db")
from app.models import RenderTask


def test_render_task_columns_exist():
    cols = {c.name for c in RenderTask.__table__.columns}
    for name in ("task_id", "user_id", "prompt", "narration", "status", "video_url", "error"):
        assert name in cols
