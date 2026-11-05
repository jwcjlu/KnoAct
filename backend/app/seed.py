"""初始化示例数据：默认用户、示例教材、词库、知识点。幂等：重复执行不产生重复数据。"""
from .database import SessionLocal, Base, engine
from .models import User, Lesson, PdfDocument, WordBank, KnowledgePoint, Text, Question, ModelConfig
from .models import ModelConnection, ModelProfile, RoleBinding, Quiz, KnowledgeMastery  # 注册到 Base.metadata，保证 create_all 建表


def _migrate_learning_progress():
    """SQLite 加列迁移：给 learning_progress 补 subject 列 + (user_id, subject) 唯一约束。

    create_all 不会改已有表，这里幂等补齐；已有行 subject 回填「语文」（历史数据均语文）。
    """
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "learning_progress" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("learning_progress")}
    with engine.begin() as conn:
        if "subject" not in cols:
            conn.execute(text("ALTER TABLE learning_progress ADD COLUMN subject VARCHAR(16) DEFAULT '语文'"))
        # 唯一约束重建：仅当旧表无该约束时创建（SQLite 需重建表才能加约束，这里用轻量方案——若旧表已有重复行会失败，
        # 但当前每 user 仅一行，安全）。为稳妥，跳过约束重建，改用应用层「按 (user_id, subject) 查询」保证不串扰。

def _migrate_pdf_document_created_at():
    """SQLite 加列迁移：给 pdf_documents 补 created_at 列（作页图缓存版本）。

    create_all 不会改已有表，这里幂等补齐；已有行回填当前时间。
    """
    from sqlalchemy import inspect, text
    from datetime import datetime
    insp = inspect(engine)
    if "pdf_documents" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("pdf_documents")}
    if "created_at" in cols:
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
    with engine.begin() as conn:
        # SQLite ADD COLUMN 不允许非常量默认值，先加空列再回填
        conn.execute(text("ALTER TABLE pdf_documents ADD COLUMN created_at DATETIME"))
        conn.execute(text("UPDATE pdf_documents SET created_at = :now"), {"now": now})


def _migrate_multi_student_columns():
    """SQLite 加列迁移：多学生 + 年级桶功能给 users / pdf_documents 补的列。

    create_all 不会改已有表，这里幂等补齐。历史孩子 grade/parent_id 留空（语义上可空），
    edition 回填空串；pdf_documents 同理。
    """
    from sqlalchemy import inspect, text
    insp = inspect(engine)

    if "users" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("users")}
        with engine.begin() as conn:
            if "grade" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN grade INTEGER"))
            if "edition" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN edition VARCHAR(64) DEFAULT ''"))
            if "parent_id" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN parent_id INTEGER"))

    if "pdf_documents" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("pdf_documents")}
        with engine.begin() as conn:
            if "edition" not in cols:
                conn.execute(text("ALTER TABLE pdf_documents ADD COLUMN edition VARCHAR(64) DEFAULT ''"))
            if "grade" not in cols:
                conn.execute(text("ALTER TABLE pdf_documents ADD COLUMN grade INTEGER"))


def _migrate_user_status():
    """SQLite 加列迁移：给 users 补 status 列（active | archived）。

    create_all 不会改已有表，这里幂等补齐；已有行默认 active。
    """
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "status" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(16) DEFAULT 'active'"))


def _migrate_bucket_columns():
    """SQLite 加列迁移：学年桶功能给业务表补 bucket_id（可空，历史数据不挂桶），
    questions 额外补 user_id。create_all 不会改已有表，这里幂等补齐。
    """
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    # 表 -> 需补的列（均为可空 INTEGER 外键，无需回填）
    needs = {
        "tasks": ["bucket_id"],
        "questions": ["bucket_id", "user_id"],
        "knowledge_mastery": ["bucket_id"],
        "points": ["bucket_id"],
        "goals": ["bucket_id"],
        "quizzes": ["bucket_id"],
        "word_mastery": ["bucket_id"],
        "mistakes": ["bucket_id"],
    }
    for table, columns in needs.items():
        if table not in existing:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        with engine.begin() as conn:
            for col in columns:
                if col not in cols:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER"))


DEFAULT_CHILD_NAME = "金同学"
_LEGACY_CHILD_NAME = "金宇轩"


def _rename_default_child(db):
    """默认孩子改名迁移：已有「金宇轩」且尚无「金同学」时原地改名，保留 id 与全部学习数据。

    前端按名字登录（/api/auth/login 找不到会新建用户），不迁移会让老数据挂在旧账号上。
    """
    if db.query(User).filter_by(name=DEFAULT_CHILD_NAME).first():
        return
    legacy = db.query(User).filter_by(name=_LEGACY_CHILD_NAME, role="child").first()
    if legacy:
        legacy.name = DEFAULT_CHILD_NAME


# 生词：word -> (拼音, 释义)
SEED_WORDS = {
    "徘徊": ("pái huái", "在一个地方来回走动，比喻犹豫不决"),
    "矗立": ("chù lì", "高耸地立着"),
    "拟人": ("nǐ rén", "把事物当作人来写的修辞手法"),
    "估计": ("gū jì", "根据情况对事物作大概的推断"),
    "璀璨": ("cuǐ càn", "形容光彩夺目"),
}

# 原型里的基础知识分类目录（无特定课文，lesson_id 为空）
SEED_KNOWLEDGE = [
    ("语文", "拼音", "声母/韵母/声调"),
    ("语文", "拼音", "拼音拼写规则"),
    ("语文", "拼音", "多音字读音"),
    ("语文", "字词", "形近字辨析"),
    ("语文", "字词", "近义词/反义词"),
    ("语文", "字词", "词语搭配"),
    ("语文", "句式", "把字句/被字句"),
    ("语文", "句式", "比喻/拟人"),
    ("语文", "句式", "标点符号"),
    ("语文", "古诗文", "名句默写"),
    ("语文", "古诗文", "作者与朝代"),
    ("语文", "古诗文", "诗句释义"),
    ("英语", "语法", "动词三单加 s"),
    ("英语", "语法", "时态变化"),
    ("英语", "语法", "名词单复数"),
    ("英语", "句型", "There be 句型"),
    ("英语", "句型", "一般疑问句"),
    ("英语", "句型", "否定句结构"),
    ("英语", "词汇用法", "词义辨析"),
    ("英语", "词汇用法", "固定搭配"),
    ("英语", "词汇用法", "介词搭配"),
    ("数学", "计算", "加减法"),
    ("数学", "计算", "乘除法"),
    ("数学", "计算", "混合运算"),
    ("数学", "图形", "平面图形"),
    ("数学", "图形", "立体图形"),
    ("数学", "应用题", "和差问题"),
    ("数学", "应用题", "倍数问题"),
]


def seed():
    Base.metadata.create_all(bind=engine)
    _migrate_learning_progress()
    _migrate_pdf_document_created_at()
    _migrate_multi_student_columns()
    _migrate_bucket_columns()
    _migrate_user_status()
    db = SessionLocal()
    _rename_default_child(db)
    if db.query(User).count() == 0:
        db.add(User(name=DEFAULT_CHILD_NAME, role="child"))
        db.add(User(name="金爸爸", role="parent"))
    if db.query(Lesson).count() == 0:
        doc = db.query(PdfDocument).first()
        if not doc:
            doc = PdfDocument(filename="示例教材.pdf", subject="语文", storage_path="uploads/示例教材.pdf")
            db.add(doc)
            db.flush()
        db.add(Lesson(document_id=doc.id, subject="语文", title="第 12 课 · 精读课文", start_page=38, end_page=41, extract_status="done", audit_status="approved"))
        db.flush()
        lid = db.query(Lesson).first().id
        for word, (pinyin, meaning) in SEED_WORDS.items():
            db.add(WordBank(lesson_id=lid, subject="语文", word=word, extra=f"{pinyin} {meaning}"))
        db.add(KnowledgePoint(subject="语文", category="字词", content="形近字辨析：似 vs 拟", lesson_id=lid))
        db.add(KnowledgePoint(subject="语文", category="句式", content="比喻与拟人的区别", lesson_id=lid))
        db.add(Text(lesson_id=lid, content="白鹭是一首精巧的诗。色素的配合，身段的大小，一切都很适宜。然而白鹭却因为它的常见，而被人忘却了它的美。"))
        db.flush()
        # 预生成阅读理解题（seed 阶段 provider 为 fake，走兜底题）
        from .services.question_gen import generate_reading_questions
        _seed_text = db.query(Text).filter_by(lesson_id=lid).first()
        for q in generate_reading_questions(db, _seed_text.content if _seed_text else "", n=3):
            db.add(Question(lesson_id=lid, qtype="reading", question=q["question"], answer=q["answer"]))
    if db.query(ModelConfig).count() == 0:
        db.add(ModelConfig(key="ai_provider", value="fake"))
        db.add(ModelConfig(key="tts_provider", value="fake"))
    # 导入原型里的基础知识分类目录（幂等：已存在则不重复插入）
    for subject, category, content in SEED_KNOWLEDGE:
        exists = db.query(KnowledgePoint).filter_by(
            subject=subject, category=category, content=content, lesson_id=None,
        ).first()
        if not exists:
            db.add(KnowledgePoint(subject=subject, category=category, content=content))
    db.commit()
    db.close()

if __name__ == "__main__":
    seed()
