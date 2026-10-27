"""独立渲染服务：把 manim 代码渲染成带旁白的视频。"""
import uuid

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .queue import TaskQueue
from .pipeline import run_pipeline, MEDIA_DIR

app = FastAPI(title="KnoAct Render Service")

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

queue = TaskQueue(max_concurrent=3)


class RenderReq(BaseModel):
    task_id: str = ""
    prompt: str
    narration: str = ""
    voice: str = ""


@app.post("/render")
def submit(req: RenderReq):
    task_id = req.task_id or uuid.uuid4().hex

    def job(tid, status_cb):
        return run_pipeline(tid, req.prompt, req.narration, req.voice, status_cb)

    queue.submit(task_id, job)
    return {"task_id": task_id, "status": "queued"}


@app.get("/render/{task_id}")
def status(task_id: str):
    s = queue.status.get(task_id)
    if s is None:
        return {"task_id": task_id, "status": "error", "video_url": None,
                "error": "任务不存在", "progress": 0}
    return {"task_id": task_id, **s}
