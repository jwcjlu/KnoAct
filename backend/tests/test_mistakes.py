from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, WordBank, Lesson, PdfDocument, Mistake

client = TestClient(app)


def _seed():
    db = SessionLocal()
    for m in (Mistake, WordBank, Lesson, PdfDocument, User):
        db.query(m).delete()
    db.commit()
    u = User(name="孩子", role="child")
    db.add(u); db.flush()
    doc = PdfDocument(filename="y.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l = Lesson(document_id=doc.id, subject="语文", title="第1课",
               start_page=1, end_page=1, extract_status="done", audit_status="approved")
    db.add(l); db.flush()
    wb = WordBank(lesson_id=l.id, subject="语文", word="白鹭", extra="pinyin")
    db.add(wb); db.flush()
    db.commit()
    return u.id, wb.id


def test_mark_correct_with_word_id_removes_only_after_gate(setup_db):
    uid, wbid = _seed()
    db = SessionLocal()
    m = Mistake(user_id=uid, source_type="dictation", question="白鹭",
                your_answer="白露", correct_answer="白鹭", word_bank_id=wbid)
    db.add(m); db.commit(); mid = m.id
    db.close()

    r1 = client.post(f"/api/mistakes/{mid}/correct").json()
    assert r1["removed"] is False   # 0.5 未达标
    r2 = client.post(f"/api/mistakes/{mid}/correct").json()
    assert r2["removed"] is False   # 0.8 未达标
    r3 = client.post(f"/api/mistakes/{mid}/correct").json()
    assert r3["removed"] is True    # 1.0 达标

    db = SessionLocal()
    assert db.get(Mistake, mid) is None
    db.close()


def test_mark_correct_without_id_uses_legacy_threshold(setup_db):
    uid, wbid = _seed()
    db = SessionLocal()
    m = Mistake(user_id=uid, source_type="reading", question="主旨是什么",
                your_answer="A", correct_answer="B")  # 无关联 id
    db.add(m); db.commit(); mid = m.id
    db.close()

    client.post(f"/api/mistakes/{mid}/correct")
    client.post(f"/api/mistakes/{mid}/correct")
    r3 = client.post(f"/api/mistakes/{mid}/correct").json()
    assert r3["removed"] is True    # 旧逻辑：连续 3 次
