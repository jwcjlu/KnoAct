"""独立渲染服务：把 manim 代码渲染成带旁白的视频。"""
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="KnoAct Render Service")


class RenderReq(BaseModel):
    task_id: str = ""
    prompt: str
    narration: str = ""
    voice: str = ""


@app.post("/render")
def submit(req: RenderReq):
    task_id = req.task_id or uuid.uuid4().hex
    return {"task_id": task_id, "status": "queued"}


@app.get("/render/{task_id}")
def status(task_id: str):
    return {"task_id": task_id, "status": "queued", "video_url": None, "error": None, "progress": 0}
