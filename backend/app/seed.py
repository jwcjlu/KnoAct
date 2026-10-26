"""初始化示例数据：默认用户、示例教材、词库、知识点。幂等：重复执行不产生重复数据。"""
from .database import SessionLocal, Base, engine
from .models import User, Lesson, PdfDocument, WordBank, KnowledgePoint, Text, Question, ModelConfig
from .models import ModelConnection, ModelProfile, RoleBinding, Quiz  # 注册到 Base.metadata，保证 create_all 建表

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
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(User).count() == 0:
        db.add(User(name="金宇轩", role="child"))
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
