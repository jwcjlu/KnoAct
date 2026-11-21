import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .routers import auth, config_router, pdf, progress, notes, points, learning, goals, mistakes, knowledge, questions, tts_router, annotations, home, tasks, quiz, mastery, render, math, users, buckets, screen_time, family, admin_users, bank, passages, xuekubao, drill, lesson_audio, knowledge_pool, answer_records, brain_games

_log = logging.getLogger("uvicorn.error")


def _warn_insecure_auth_env() -> None:
    """生产部署应设置强 JWT_SECRET 与非默认管理员初始密码（ID-04）。pytest 不告警。"""
    if "pytest" in sys.modules:
        return
    jwt_secret = os.environ.get("JWT_SECRET", "dev-change-me")
    if jwt_secret in ("", "dev-change-me"):
        _log.warning(
            "KnoAct: JWT_SECRET 未设置或为 dev 默认值；生产环境请设置长随机密钥（见 README 与 .env.example）"
        )
    admin_pwd = os.environ.get("ADMIN_INITIAL_PASSWORD", "ChangeMe123")
    if admin_pwd == "ChangeMe123":
        _log.warning(
            "KnoAct: ADMIN_INITIAL_PASSWORD 为默认值 ChangeMe123；"
            "种子会为 admin 等账号使用该密码，生产上线后请立即修改"
        )


app = FastAPI(title="知学伴 API")


@app.on_event("startup")
def _ensure_db_tables() -> None:
    """对照模型补缺失的表和列。create_all 只建新表，老表缺列由 schema_sync 补。"""
    if "pytest" in sys.modules:
        return
    from .database import SessionLocal
    from .models import Base  # noqa: F401 — 注册全部表
    from .database import engine
    from .schema_sync import sync_schema
    try:
        sync_schema(engine, Base.metadata)
    except Exception as exc:
        _log.warning("启动时补表/补列失败: %s", exc)
    db = SessionLocal()
    try:
        try:
            from .migrate_question_bank import migrate as _migrate_question_bank

            _migrate_question_bank(db)
        except Exception as exc:
            db.rollback()
            _log.warning("questions 题库列迁移失败: %s", exc)
        try:
            from .migrate_reading_passage import migrate as _migrate_reading_passage

            _migrate_reading_passage(db)
        except Exception as exc:
            db.rollback()
            _log.warning("questions.passage_id 迁移失败: %s", exc)
        try:
            from .migrate_grade_buckets import migrate as _migrate_grade_buckets

            _migrate_grade_buckets(db)
        except Exception as exc:
            db.rollback()
            _log.warning("child grade/桶回填失败: %s", exc)
        try:
            from .migrate_practice_import import migrate as _migrate_practice_import

            _migrate_practice_import()
        except Exception as exc:
            _log.warning("练习册导入迁移失败: %s", exc)
    finally:
        db.close()


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
app.include_router(family.router)
app.include_router(admin_users.router)
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
app.include_router(quiz.router)
app.include_router(mastery.router)
app.include_router(render.router)
app.include_router(math.router)
app.include_router(users.router)
app.include_router(users.children_router)
app.include_router(buckets.router)
app.include_router(screen_time.router)
app.include_router(bank.router)
app.include_router(passages.router)
app.include_router(xuekubao.router)
app.include_router(drill.router)
app.include_router(lesson_audio.router)
app.include_router(knowledge_pool.router)
app.include_router(answer_records.router)
app.include_router(brain_games.router)

_warn_insecure_auth_env()

# 每天 03:00 定时生成当天任务（模块级调度器，pytest 导入时不启动）
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
