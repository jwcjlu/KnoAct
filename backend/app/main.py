from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .routers import auth, config_router, pdf, progress, notes, points, learning, goals, mistakes, knowledge, questions, tts_router, annotations, home, tasks

app = FastAPI(title="知学伴 API")

# 开发阶段放开跨域，便于前端本地联调
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 暴露 PDF 渲染页图片（uploads/{doc.id}_pages/*.png）
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(auth.router)
app.include_router(config_router.router)
app.include_router(pdf.router)
app.include_router(progress.router)
app.include_router(notes.router)
app.include_router(points.router)
app.include_router(learning.router)
app.include_router(goals.router)
app.include_router(mistakes.router)
app.include_router(knowledge.router)
app.include_router(questions.router)
app.include_router(tts_router.router)
app.include_router(annotations.router)
app.include_router(home.router)
app.include_router(tasks.router)

# 每天 03:00 定时生成当天任务（模块级调度器，pytest 导入时不启动）
import sys
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .database import SessionLocal
from .services.task_gen import generate_daily_tasks


def _scheduled_generate() -> None:
    db = SessionLocal()
    try:
        generate_daily_tasks(db, date.today())
    finally:
        db.close()


if "pytest" not in sys.modules:
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _scheduled_generate,
        CronTrigger(hour=3, minute=0),
        id="daily_tasks",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
