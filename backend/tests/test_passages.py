from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Question, QuestionBank, ReadingPassage
from conftest import auth_headers, make_account

client = TestClient(app)


def _parent_with_bank():
    db = SessionLocal()
    p = make_account(db, "pass_parent", "parent")
    bank = QuestionBank(user_id=p.id, title="语文卷", subject="语文", source="manual")
    db.add(bank)
    db.commit()
    headers = auth_headers(p)
    bid, pid = bank.id, p.id
    db.close()
    return headers, bid, pid


def test_create_passage_with_questions(client, setup_db):
    h, bid, _ = _parent_with_bank()
    body = {
        "title": "小蝌蚪找妈妈",
        "content": "小蝌蚪 **游啊游**。它们看见 ____。",
        "subject": "语文",
        "bank_id": bid,
        "questions": [
            {"qtype": "fill_blank", "question": "它们看见了什么？", "answer": "鲤鱼", "answer_json": {"blanks": ["鲤鱼"]}},
            {"qtype": "short_answer", "question": "小蝌蚪在做什么？", "answer": "找妈妈", "answer_json": {"sample": "找妈妈", "rubric": ""}},
        ],
    }
    r = client.post("/api/passages", json=body, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] > 0
    assert len(data["question_ids"]) == 2
    db = SessionLocal()
    psg = db.get(ReadingPassage, data["id"])
    assert psg.title == "小蝌蚪找妈妈"
    assert psg.status == "pending"
    assert psg.bank_id == bid
    qs = db.query(Question).filter_by(passage_id=psg.id).order_by(Question.id).all()
    db.close()
    assert len(qs) == 2
    assert qs[0].qtype == "fill_blank"
    assert qs[0].qtype_category == "blank"
    assert qs[0].status == "pending"
    assert qs[0].bank_id == bid
    assert qs[1].qtype == "short_answer"


def test_create_passage_rejects_blank_mismatch(client, setup_db):
    h, bid, _ = _parent_with_bank()
    body = {
        "title": "不对齐", "content": "只有一处 ____", "bank_id": bid,
        "questions": [
            {"qtype": "fill_blank", "question": "空1", "answer_json": {"blanks": ["a"]}},
            {"qtype": "fill_blank", "question": "空2", "answer_json": {"blanks": ["b"]}},
        ],
    }
    r = client.post("/api/passages", json=body, headers=h)
    assert r.status_code == 400


def test_get_passage_returns_questions(client, setup_db):
    h, bid, _ = _parent_with_bank()
    r = client.post("/api/passages", json={
        "title": "短文", "content": "正文", "bank_id": bid,
        "questions": [{"qtype": "short_answer", "question": "主旨？", "answer": "春天"}],
    }, headers=h)
    pid = r.json()["id"]
    g = client.get(f"/api/passages/{pid}", headers=h)
    assert g.status_code == 200
    data = g.json()
    assert data["title"] == "短文"
    assert data["content"] == "正文"
    assert len(data["questions"]) == 1
    assert data["questions"][0]["question"] == "主旨？"


def test_list_passages_by_bank(client, setup_db):
    h, bid, _ = _parent_with_bank()
    client.post("/api/passages", json={"title": "A", "content": "c", "bank_id": bid}, headers=h)
    r = client.get(f"/api/passages?bank_id={bid}", headers=h)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 1
    assert rows[0]["title"] == "A"
    assert rows[0]["question_count"] == 0
