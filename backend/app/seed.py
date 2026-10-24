"""初始化示例数据：默认用户、示例教材、词库、知识点。幂等：重复执行不产生重复数据。"""
from .database import SessionLocal, Base, engine
from .models import User, Lesson, WordBank, KnowledgePoint, Text, ModelConfig

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(User).count() == 0:
        db.add(User(name="林晨", role="child"))
        db.add(User(name="家长", role="parent"))
    if db.query(Lesson).count() == 0:
        db.add(Lesson(document_id=1, subject="语文", title="第 12 课 · 精读课文", start_page=38, end_page=41, extract_status="done", audit_status="approved"))
        db.flush()
        lid = db.query(Lesson).first().id
        for w in ["徘徊", "矗立", "拟人", "估计", "璀璨"]:
            db.add(WordBank(lesson_id=lid, subject="语文", word=w, extra="拼音+释义（示例）"))
        db.add(KnowledgePoint(subject="语文", category="字词", content="形近字辨析：似 vs 拟"))
        db.add(Text(lesson_id=lid, content="白鹭是一首精巧的诗。"))
    if db.query(ModelConfig).count() == 0:
        db.add(ModelConfig(key="ai_provider", value="fake"))
        db.add(ModelConfig(key="tts_provider", value="fake"))
    db.commit()
    db.close()

if __name__ == "__main__":
    seed()
