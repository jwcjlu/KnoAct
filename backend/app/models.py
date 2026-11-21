from datetime import datetime, date
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, Text as TextCls, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

# MySQL 的 TEXT 上限 64KB（中文约 2 万字），课文/上下文等长文本在 MySQL 上用 MEDIUMTEXT
LongText = TextCls().with_variant(MEDIUMTEXT(), "mysql")

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    login_name: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    display_name: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(16))  # 'parent' | 'child' | 'admin'
    grade: Mapped[int] = mapped_column(Integer, nullable=True)  # 当前年级 1~6
    edition: Mapped[str] = mapped_column(String(64), default="")  # 教材版本（人教版/苏教版…）
    parent_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)  # 所属家长
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | archived
    birth_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    gender: Mapped[str] = mapped_column(String(16), default="unknown")
    interests: Mapped[str] = mapped_column(LongText, default="")
    phone: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(128), default="")
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

class PdfDocument(Base):
    __tablename__ = "pdf_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(16))  # '语文' | '英语' | '数学'
    storage_path: Mapped[str] = mapped_column(String(512))
    edition: Mapped[str] = mapped_column(String(64), default="")  # 教材版本（人教版/苏教版…）
    grade: Mapped[int] = mapped_column(Integer, nullable=True)  # 年级 1~6
    content_kind: Mapped[str] = mapped_column(String(16), default="textbook")  # textbook | handout
    handout_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)  # phrase | outline
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # 作页图缓存版本（拼 ?v=）

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

class LessonAudio(Base):
    __tablename__ = "lesson_audios"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))
    unit_label: Mapped[str] = mapped_column(String(255))
    audio_path: Mapped[str] = mapped_column(String(255))
    marks_json: Mapped[str] = mapped_column(LongText, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "subject", name="uq_progress_user_subject"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(16), default="语文")  # '语文' | '英语' | '数学'
    current_lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=True)

class WordBank(Base):
    __tablename__ = "word_banks"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    subject: Mapped[str] = mapped_column(String(16))
    word: Mapped[str] = mapped_column(String(64))
    extra: Mapped[str] = mapped_column(LongText, default="")  # 拼音/音标/词性/释义，按学科

class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(LongText)

class Text(Base):
    __tablename__ = "texts"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    content: Mapped[str] = mapped_column(LongText)

class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_bank_lesson", "bank_id", "lesson_no"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=True)  # 改 nullable：可独立成题
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"), nullable=True)  # 归属的卷
    passage_id: Mapped[int] = mapped_column(ForeignKey("reading_passages.id"), nullable=True)  # 阅读材料子题；独立题为 NULL
    qtype: Mapped[str] = mapped_column(String(16), default="reading")   # 旧值 reading/listening/...；新值 taxonomy（single_choice 等），经 LEGACY_QTYPE_MAP 迁移
    qtype_category: Mapped[str] = mapped_column(String(16), default="subjective")  # choice|blank|match|subjective
    question: Mapped[str] = mapped_column(LongText)
    answer: Mapped[str] = mapped_column(LongText, default="")
    answer_json: Mapped[str] = mapped_column(LongText, default="")       # 机器判分依据 JSON
    options: Mapped[str] = mapped_column(LongText, default="")           # 选择/连线题选项 JSON
    analysis: Mapped[str] = mapped_column(LongText, default="")          # 解析
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")  # easy|medium|hard
    tags: Mapped[str] = mapped_column(LongText, default="")              # {grade, knowledge_points, source} JSON
    subject: Mapped[str] = mapped_column(String(16), default="")         # 学科：语文/英语/数学
    date: Mapped[date] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="published")
    extra: Mapped[str] = mapped_column(LongText, default="")
    task_type: Mapped[str] = mapped_column(String(16), default="reading")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 练习册导入用：课时号/课时标题/题号（可索引，便于按课时取题）
    lesson_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lesson_title: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question_no: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 来源文档（练习册导入题才填）；删文档时置 NULL，题目保留
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("pdf_documents.id", ondelete="SET NULL"), nullable=True)
    # 图片题：题干主体在图里（几何/统计题），存裁好的题目图路径
    image_path: Mapped[str] = mapped_column(String(512), default="")


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    author_role: Mapped[str] = mapped_column(String(16))  # child | parent
    content: Mapped[str] = mapped_column(LongText)
    anchor_text: Mapped[str] = mapped_column(LongText, default="")
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Annotation(Base):
    __tablename__ = "annotations"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), default=0)
    kind: Mapped[str] = mapped_column(String(16))           # highlight | underline | note | glossary
    quote: Mapped[str] = mapped_column(LongText)             # 被选中的原文片段
    note: Mapped[str] = mapped_column(LongText, default="")  # 笔记内容 / 生词释义
    color: Mapped[str] = mapped_column(String(16), default="yellow")
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    # 归一化矩形坐标（JSON 文本，如 [[x0,y0,x1,y1],...]，0~1 相对页宽高），
    # 用于在原文上精确铺高亮/下划线，对齐 DeepTutor 的 normalised rects 机制。
    rects: Mapped[str] = mapped_column(LongText, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class WordMastery(Base):
    __tablename__ = "word_mastery"
    id: Mapped[int] = mapped_column(primary_key=True)
    word_bank_id: Mapped[int] = mapped_column(ForeignKey("word_banks.id"))
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    mistake_count: Mapped[int] = mapped_column(Integer, default=0)
    is_weak: Mapped[bool] = mapped_column(Boolean, default=False)
    next_review_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)  # 迁移回填
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    attempts: Mapped[str] = mapped_column(LongText, default="[]")
    mastery: Mapped[float] = mapped_column(Float, default=0.0)

class Mistake(Base):
    __tablename__ = "mistakes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32))  # dictation | review | listening | reading | goal
    question: Mapped[str] = mapped_column(LongText)
    your_answer: Mapped[str] = mapped_column(LongText)
    correct_answer: Mapped[str] = mapped_column(LongText)
    mistake_count: Mapped[int] = mapped_column(Integer, default=1)
    consecutive_correct: Mapped[int] = mapped_column(Integer, default=0)
    word_bank_id: Mapped[int] = mapped_column(ForeignKey("word_banks.id"), nullable=True)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True)

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
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    content: Mapped[str] = mapped_column(LongText)
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
    value: Mapped[str] = mapped_column(LongText, default="")

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "subject", "date", "task_type", name="uq_task_user_subject_date_type"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16))            # '语文' | '英语'
    date: Mapped[date] = mapped_column(Date)                    # 任务所属日期
    task_type: Mapped[str] = mapped_column(String(16))          # dictation|knowledge|review|reading|listening|math|practice|drill|custom
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(LongText, default="")   # JSON 文本快照
    points: Mapped[int] = mapped_column(Integer, default=20)
    content_status: Mapped[str] = mapped_column(String(16), default="pending_review")  # pending_review|published
    submit_status: Mapped[str] = mapped_column(String(16), default="not_started")      # not_started|submitted|approved
    photo_path: Mapped[str] = mapped_column(String(512), default="")
    reviewed_by: Mapped[int] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=True)  # 预留，本次恒 null
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ModelConnection(Base):
    """一套凭证 + 端点，可被多个角色复用。"""
    __tablename__ = "model_connections"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))     # openai|deepseek|glm|minimax|xunfei|fake
    name: Mapped[str] = mapped_column(String(128), default="")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    api_key: Mapped[str] = mapped_column(String(512), default="")
    extra_headers: Mapped[str] = mapped_column(LongText, default="")  # JSON 文本
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ModelProfile(Base):
    """某角色下的一档模型选择。"""
    __tablename__ = "model_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(16))          # llm|task|embedding|search|tts|stt|imagegen
    connection_id: Mapped[int] = mapped_column(ForeignKey("model_connections.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    name: Mapped[str] = mapped_column(String(128), default="")
    options: Mapped[str] = mapped_column(LongText, default="")  # JSON 文本
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RoleBinding(Base):
    """角色 → 当前启用哪一档。主键即 role。"""
    __tablename__ = "role_bindings"
    role: Mapped[str] = mapped_column(String(16), primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("model_profiles.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="inherit")  # 仅 task 使用


class Quiz(Base):
    """边读边问·测验：题目 + 服务端答案 key。"""
    __tablename__ = "quizzes"
    id: Mapped[int] = mapped_column(primary_key=True)          # 即 quiz_id
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    questions: Mapped[str] = mapped_column(LongText)            # JSON：[{id,prompt,choices,correct_index,evidence}]
    score: Mapped[int] = mapped_column(Integer, nullable=True) # None=未作答
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeMastery(Base):
    """知识点级掌握度。"""
    __tablename__ = "knowledge_mastery"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"))
    attempts: Mapped[str] = mapped_column(LongText, default="[]")  # JSON：[true, false, ...]
    mastery: Mapped[float] = mapped_column(Float, default=0.0)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    next_review_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Turn(Base):
    """一次 agent turn：一个提问 → 一次多步工具循环 → 最终答案。"""
    __tablename__ = "turns"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    capability: Mapped[str] = mapped_column(String(32))   # chat | visualize | solve
    mode: Mapped[str] = mapped_column(String(16))          # 冗余存原始 mode
    question: Mapped[str] = mapped_column(LongText)
    context: Mapped[str] = mapped_column(LongText, default="")
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|done|error
    final_answer: Mapped[str] = mapped_column(LongText, default="")
    citations: Mapped[str] = mapped_column(LongText, default="[]")  # JSON 数组文本
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class ToolCall(Base):
    """一次 turn 内的一次工具调用（含 args + result，可 replay）。"""
    __tablename__ = "tool_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turns.id"))
    step: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(64))
    args: Mapped[str] = mapped_column(LongText, default="{}")   # JSON 文本
    result: Mapped[str] = mapped_column(LongText, default="{}")  # JSON 文本
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RenderTask(Base):
    """一次 manim 动画渲染任务（提交给独立渲染服务）。"""
    __tablename__ = "render_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    turn_id: Mapped[int] = mapped_column(ForeignKey("turns.id"), nullable=True)
    prompt: Mapped[str] = mapped_column(LongText, default="")
    narration: Mapped[str] = mapped_column(LongText, default="")
    status: Mapped[str] = mapped_column(String(16), default="submitted")
    video_url: Mapped[str] = mapped_column(String(255), default="")
    error: Mapped[str] = mapped_column(LongText, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SchoolYearBucket(Base):
    """一个孩子的一个学年「桶」：升年级即封存旧桶、开新桶，历史数据按桶归档。"""
    __tablename__ = "school_year_buckets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    grade: Mapped[int] = mapped_column(Integer)
    school_year: Mapped[str] = mapped_column(String(16))          # 如 "2025-2026"
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | archived


class ChildConfig(Base):
    """孩子对全局配置的覆盖项；未配则回落全局 ModelConfig。跨学年沿用，不分桶。"""
    __tablename__ = "child_config"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_child_config_user_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(LongText, default="")


class UserDocument(Base):
    """孩子 ↔ 教材 绑定：孩子能看哪些教材由家长显式选配；一本可绑多孩子（共享）。"""
    __tablename__ = "user_documents"
    __table_args__ = (
        UniqueConstraint("user_id", "document_id", name="uq_user_document"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))


class TrainingGroup(Base):
    """专项训练组：讲义=节，自录=一组条目。"""
    __tablename__ = "training_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(16))            # handout | custom
    kind: Mapped[str] = mapped_column(String(16))              # phrase | outline | explore
    document_id: Mapped[int | None] = mapped_column(ForeignKey("pdf_documents.id"), nullable=True)
    start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mastery_interval_days: Mapped[int] = mapped_column(Integer, default=15)
    interval_max_days: Mapped[int] = mapped_column(Integer, default=60)
    group_rule: Mapped[str] = mapped_column(LongText, default="")   # JSON {examples,question,reveal}
    intro: Mapped[str] = mapped_column(LongText, default="")        # JSON {situation,goal,route}
    ai_review: Mapped[str] = mapped_column(LongText, default="[]")  # JSON 发布前 AI 预检的疑似问题列表
    audit_status: Mapped[str] = mapped_column(String(16), default="pending")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class TrainingItem(Base):
    """专项训练条目：最小记忆/探究单元。"""
    __tablename__ = "training_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("training_groups.id"))
    kind: Mapped[str] = mapped_column(String(16))   # phrase | outline_point | drill_item | explore
    primary: Mapped[str] = mapped_column(LongText)
    secondary: Mapped[str] = mapped_column(LongText, default="")
    block_title: Mapped[str] = mapped_column(String(255), default="")
    example: Mapped[str] = mapped_column(LongText, default="")
    keywords: Mapped[str] = mapped_column(LongText, default="[]")
    common_mistake: Mapped[str] = mapped_column(LongText, default="")  # JSON {wrong,correct,explain}
    explore: Mapped[str] = mapped_column(LongText, default="{}")       # JSON {compare,classify,formula,trap}
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    point_pool_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_point_pool.id"), nullable=True)


class TrainingItemMastery(Base):
    """专项条目 SRS 掌握度。mastered 不落库，实时判定。"""
    __tablename__ = "training_item_mastery"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("training_items.id"))
    bucket_id: Mapped[int | None] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    interval: Mapped[int] = mapped_column(Integer, default=1)
    lapse: Mapped[int] = mapped_column(Integer, default=0)
    last_hinted: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[str] = mapped_column(LongText, default="[]")
    next_review_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class AppGroup(Base):
    """屏幕时间 App 分组；kind: learn=学习 / fun=娱乐 / custom=自定义。"""
    __tablename__ = "app_groups"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_app_group_user_name"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16), default="custom")  # learn | fun | custom
    daily_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=True)  # 空 = 不限


class AppRule(Base):
    """App 包名 → 分组的映射。"""
    __tablename__ = "app_rules"
    __table_args__ = (
        UniqueConstraint("user_id", "app_package", name="uq_app_rule_user_package"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    app_package: Mapped[str] = mapped_column(String(255))
    app_name: Mapped[str] = mapped_column(String(255), default="")
    group_id: Mapped[int] = mapped_column(ForeignKey("app_groups.id"))


class ScreenUsage(Base):
    """每孩子每天每 App 的前台使用时长（上报去重累加）。"""
    __tablename__ = "screen_usage"
    __table_args__ = (
        UniqueConstraint("child_id", "date", "app_package", name="uq_screen_usage_child_date_pkg"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    app_package: Mapped[str] = mapped_column(String(255))
    app_name: Mapped[str] = mapped_column(String(255), default="")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    group_id: Mapped[int] = mapped_column(ForeignKey("app_groups.id"), nullable=True)


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    channel: Mapped[str] = mapped_column(String(16))  # phone | email
    purpose: Mapped[str] = mapped_column(String(32))  # login | reset_password | bind_phone
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class FamilyInvite(Base):
    __tablename__ = "family_invites"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_by_child_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class FamilyBindRequest(Base):
    __tablename__ = "family_bind_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    parent_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | approved | rejected


class QuestionBank(Base):
    """家长自建的一册卷子/题库；一道题可挂卷、挂课、或都不挂只靠 tags 检索。"""
    __tablename__ = "question_banks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(16), default="")
    grade: Mapped[int] = mapped_column(Integer, nullable=True)
    tags: Mapped[str] = mapped_column(LongText, default="")   # JSON 文本
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual|photo|third_party
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|archived
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReadingPassage(Base):
    """阅读理解材料。子题挂 Question.passage_id，不新增 qtype。"""
    __tablename__ = "reading_passages"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(LongText, default="")
    grade: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | published
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeFolder(Base):
    """知识点库目录：parent_id 多级，按家长隔离。"""
    __tablename__ = "knowledge_folders"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(128))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_folders.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgePointPool(Base):
    """知识点库：讲义 PDF 解析出的可复用知识点，按家长隔离。"""
    __tablename__ = "knowledge_point_pool"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(16))            # 语文/英语/数学
    category: Mapped[str] = mapped_column(String(32), default="")  # 短语/句型/语法/生字/古诗…
    content: Mapped[str] = mapped_column(LongText)              # 知识点主体（如 look after）
    extra: Mapped[str] = mapped_column(LongText, default="{}")  # JSON：释义/例句/音标/作者
    source: Mapped[str] = mapped_column(String(16), default="manual")  # pdf | manual
    document_id: Mapped[int | None] = mapped_column(ForeignKey("pdf_documents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_folders.id"), nullable=True)
    tags: Mapped[str] = mapped_column(LongText, default="[]")  # JSON 数组，如 ["易错","重点"]


class TrainingPlan(Base):
    """训练方案：家长勾选知识点组合，可保存/编辑/发布成专项训练。"""
    __tablename__ = "training_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    point_ids: Mapped[str] = mapped_column(LongText, default="[]")   # JSON 数组，如 [3,7,12]
    group_id: Mapped[int | None] = mapped_column(ForeignKey("training_groups.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | published
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnswerRecord(Base):
    """做题明细：每次作答一行，家长端「当天做题明细」监管用。"""
    __tablename__ = "answer_records"
    __table_args__ = (
        Index("ix_answer_records_user_created", "user_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_id: Mapped[int | None] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16), default="")
    module: Mapped[str] = mapped_column(String(32), default="")
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    question: Mapped[str] = mapped_column(LongText)
    student_answer: Mapped[str] = mapped_column(LongText, default="")
    correct_answer: Mapped[str] = mapped_column(LongText, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    difficulty: Mapped[str] = mapped_column(String(16), default="")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), default="")
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BrainGameResult(Base):
    """思维训练小游戏成绩：客户端本地出题，后端只记录结果用于统计最佳。

    不写 AnswerRecord（游戏不是做题，避免污染家长端「当天做题明细」），
    也不涉及积分。
    """
    __tablename__ = "brain_game_results"
    __table_args__ = (
        Index("ix_brain_game_results_user_bucket_game",
              "user_id", "bucket_id", "game", "difficulty"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bucket_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_year_buckets.id"), nullable=True)
    game: Mapped[str] = mapped_column(String(24))        # sudoku | schulte | minesweeper
    difficulty: Mapped[str] = mapped_column(String(12))  # easy | medium | hard
    duration_ms: Mapped[int] = mapped_column(Integer)
    moves: Mapped[int] = mapped_column(Integer, default=0)
    solved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PracticeImportJob(Base):
    """练习册 PDF 导入任务：进度、页码范围、识别/对齐/发布计数。"""
    __tablename__ = "practice_import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending | ocr | aligning | done | failed
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    done_pages: Mapped[int] = mapped_column(Integer, default=0)
    question_start_page: Mapped[int] = mapped_column(Integer, default=1)
    question_end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    aligned_count: Mapped[int] = mapped_column(Integer, default=0)
    published_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_pages: Mapped[str] = mapped_column(LongText, default="[]")
    error: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PracticeAttempt(Base):
    """逐题作答（计划二写入，计划三家长查看；计划一先建表，避免二次迁移）。"""
    __tablename__ = "practice_attempts"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", "date", name="uq_practice_attempt"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"))
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"))
    date: Mapped[date] = mapped_column(Date)
    lesson_no: Mapped[int] = mapped_column(Integer, default=0)
    question_snapshot: Mapped[str] = mapped_column(LongText, default="")
    student_answer: Mapped[str] = mapped_column(LongText, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_path: Mapped[str] = mapped_column(String(512), default="")
    ai_status: Mapped[str] = mapped_column(String(16), default="")
    ai_final_answer: Mapped[str] = mapped_column(String(64), default="")
    ai_steps_plausible: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_reason: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
