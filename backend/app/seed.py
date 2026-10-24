"""初始化示例数据：默认用户、示例教材、词库、知识点。幂等：重复执行不产生重复数据。"""
from .database import SessionLocal, Base, engine
from .models import User, Lesson, PdfDocument, WordBank, KnowledgePoint, Text, ModelConfig

# 生词：word -> (拼音, 释义)
SEED_WORDS = {
    "徘徊": ("pái huái", "在一个地方来回走动，比喻犹豫不决"),
    "矗立": ("chù lì", "高耸地立着"),
    "拟人": ("nǐ rén", "把事物当作人来写的修辞手法"),
    "估计": ("gū jì", "根据情况对事物作大概的推断"),
    "璀璨": ("cuǐ càn", "形容光彩夺目"),
}

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(User).count() == 0:
        db.add(User(name="林晨", role="child"))
        db.add(User(name="家长", role="parent"))
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
    if db.query(ModelConfig).count() == 0:
        db.add(ModelConfig(key="ai_provider", value="fake"))
        db.add(ModelConfig(key="tts_provider", value="fake"))
    db.commit()
    db.close()

if __name__ == "__main__":
    seed()
