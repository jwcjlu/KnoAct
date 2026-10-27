"""渲染任务状态查询 + 视频代理。"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import RenderTask

router = APIRouter(tags=["render"])

RENDER_SERVICE_URL = "http://127.0.0.1:8011"


@router.get("/api/render/{task_id}")
def render_status(task_id: str, db: Session = Depends(get_db)):
    row = db.query(RenderTask).filter_by(task_id=task_id).first()
    if row is None:
        raise HTTPException(404, "任务不存在")

    # 中间态：透传问渲染服务，更新本地缓存
    if row.status in ("submitted", "queued", "generating", "rendering", "mixing"):
        try:
            import requests
            r = requests.get(f"{RENDER_SERVICE_URL}/render/{task_id}", timeout=3)
            if r.status_code == 200:
                s = r.json()
                row.status = s.get("status", row.status)
                if s.get("video_url"):
                    row.video_url = s["video_url"]
                if s.get("error"):
                    row.error = s["error"]
                row.updated_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass  # 渲染服务没起就保持本地状态

    video_url = ""
    if row.status == "done" and row.video_url:
        video_url = f"http://127.0.0.1:8010/render_media/{row.video_url}"
    return {"task_id": task_id, "status": row.status, "video_url": video_url,
            "error": row.error}


@router.get("/render_media/{path:path}")
def render_media(path: str):
    """把渲染服务的媒体文件代理给前端（前端不直连渲染服务）。"""
    # 防路径穿越：拒绝 .. 和绝对路径，只允许 MEDIA_DIR 内的相对路径
    if ".." in path or path.startswith("/") or "\\" in path:
        raise HTTPException(400, "非法路径")
    url = f"{RENDER_SERVICE_URL}/media/{path}"
    import requests
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        raise HTTPException(404, "视频不存在")
    return Response(content=r.content, media_type="video/mp4")
