from datetime import datetime, date
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, Text as TextCls, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))  # 'parent' | 'child'

class PdfDocument(Base):
    __tablename__ = "pdf_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(16))  # '语文' | '英语' | '数学'
    storage_path: Mapped[str] = mapped_column(String(512))

class PdfPage(Base):
    __tablename__ = "pdf_pages"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))
    page_number: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str] = mapped_column(String(512))

class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))
    subject: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    start_page: Mapped[int] = mapped_column(Integer)
    end_page: Mapped[int] = mapped_column(Integer)
    extract_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | done
    audit_status: Mapped[str] = mapped_column(String(16), default="pending")    # pending | approved | rejected

class Textbook(Base):
    __tablename__ = "textbooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))
    subject: Mapped[str] = mapped_column(String(16))
    unit: Mapped[str] = mapped_column(String(255))

class LearningProgress(Base):
    __tablename__ = "learning_progress"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    current_lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=True)

class WordBank(Base):
    __tablename__ = "word_banks"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    subject: Mapped[str] = mapped_column(String(16))
    word: Mapped[str] = mapped_column(String(64))
    extra: Mapped[str] = mapped_column(TextCls, default="")  # 拼音/音标/词性/释义，按学科

class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(TextCls)

class Text(Base):
    __tablename__ = "texts"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    content: Mapped[str] = mapped_column(TextCls)

class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    qtype: Mapped[str] = mapped_column(String(16), default="reading")   # reading | listening
    question: Mapped[str] = mapped_column(TextCls)
    answer: Mapped[str] = mapped_column(TextCls, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    author_role: Mapped[str] = mapped_column(String(16))  # child | parent
    content: Mapped[str] = mapped_column(TextCls)
    anchor_text: Mapped[str] = mapped_column(TextCls, default="")
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Annotation(Base):
    __tablename__ = "annotations"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), default=0)
    kind: Mapped[str] = mapped_column(String(16))           # highlight | underline | note | glossary
    quote: Mapped[str] = mapped_column(TextCls)             # 被选中的原文片段
    note: Mapped[str] = mapped_column(TextCls, default="")  # 笔记内容 / 生词释义
    color: Mapped[str] = mapped_column(String(16), default="yellow")
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    # 归一化矩形坐标（JSON 文本，如 [[x0,y0,x1,y1],...]，0~1 相对页宽高），
    # 用于在原文上精确铺高亮/下划线，对齐 DeepTutor 的 normalised rects 机制。
    rects: Mapped[str] = mapped_column(TextCls, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class WordMastery(Base):
    __tablename__ = "word_mastery"
    id: Mapped[int] = mapped_column(primary_key=True)
    word_bank_id: Mapped[int] = mapped_column(ForeignKey("word_banks.id"))
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    mistake_count: Mapped[int] = mapped_column(Integer, default=0)
    is_weak: Mapped[bool] = mapped_column(Boolean, default=False)
    next_review_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

class Mistake(Base):
    __tablename__ = "mistakes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_type: Mapped[str] = mapped_column(String(32))  # dictation | review | listening | reading | goal
    question: Mapped[str] = mapped_column(TextCls)
    your_answer: Mapped[str] = mapped_column(TextCls)
    correct_answer: Mapped[str] = mapped_column(TextCls)
    mistake_count: Mapped[int] = mapped_column(Integer, default=1)
    consecutive_correct: Mapped[int] = mapped_column(Integer, default=0)

class LearningRecord(Base):
    __tablename__ = "learning_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    task_type: Mapped[str] = mapped_column(String(32))
    correct: Mapped[int] = mapped_column(Integer, default=0)
    wrong: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Point(Base):
    __tablename__ = "points"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(TextCls)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | in_progress | done
    achieved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

class Reward(Base):
    __tablename__ = "rewards"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    device: Mapped[str] = mapped_column(String(32))  # tablet | phone
    minutes: Mapped[int] = mapped_column(Integer)
    points_cost: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ModelConfig(Base):
    __tablename__ = "model_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)   # ai_provider / ai_model / ai_key / tts_provider / tts_voice / tts_key / tts_speed / tts_repeat
    value: Mapped[str] = mapped_column(TextCls, default="")

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "subject", "date", "task_type", name="uq_task_user_subject_date_type"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(16))            # '语文' | '英语'
    date: Mapped[date] = mapped_column(Date)                    # 任务所属日期
    task_type: Mapped[str] = mapped_column(String(16))          # dictation|knowledge|review|reading|listening|custom
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(TextCls, default="")   # JSON 文本快照
    points: Mapped[int] = mapped_column(Integer, default=20)
    content_status: Mapped[str] = mapped_column(String(16), default="pending_review")  # pending_review|published
    submit_status: Mapped[str] = mapped_column(String(16), default="not_started")      # not_started|submitted|approved
    photo_path: Mapped[str] = mapped_column(String(512), default="")
    reviewed_by: Mapped[int] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=True)  # 预留，本次恒 null
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
