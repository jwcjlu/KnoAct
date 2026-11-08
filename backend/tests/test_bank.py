from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Question, QuestionBank
from conftest import auth_headers, make_account

client = TestClient(app)


def _parent_headers():
    db = SessionLocal()
    p = make_account(db, "bank_parent", "parent")
    headers = auth_headers(p)
    db.close()
    return headers


def _seed_bank_with_question(status="published"):
    """建一个家长 + 卷 + 一道单选题，返回 (parent_headers, bank_id, question_id)。"""
    db = SessionLocal()
    p = make_account(db, "bank_seed_parent", "parent")
    bank = QuestionBank(user_id=p.id, title="测试卷", subject="数学", source="manual")
    db.add(bank)
    db.flush()
    q = Question(bank_id=bank.id, qtype="single_choice", qtype_category="choice",
                 question="1+1=?", options='[{"label":"2","value":0},{"label":"1","value":1}]',
                 answer_json='{"correct_index":0}', answer="2", status=status)
    db.add(q)
    db.commit()
    headers = auth_headers(p)
    bid = bank.id
    qid = q.id
    db.close()
    return headers, bid, qid


def test_create_bank(client, setup_db):
    h = _parent_headers()
    r = client.post("/api/banks", json={"title": "三年级数学期末卷", "subject": "数学", "grade": 3}, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] > 0


def test_list_banks(client, setup_db):
    h = _parent_headers()
    client.post("/api/banks", json={"title": "卷A", "subject": "数学"}, headers=h)
    r = client.get("/api/banks", headers=h)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_submit_grades_published_choice(client, setup_db):
    h, bank_id, qid = _seed_bank_with_question(status="published")
    r = client.post("/api/banks/submit",
                    json={"bank_id": bank_id, "answers": [{"question_id": qid, "selected_index": 0}]},
                    headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == 1
    assert data["answers"][0]["is_correct"] is True


def test_submit_ignores_draft_question(client, setup_db):
    h, bank_id, qid = _seed_bank_with_question(status="pending")
    r = client.post("/api/banks/submit",
                    json={"bank_id": bank_id, "answers": [{"question_id": qid, "selected_index": 0}]},
                    headers=h)
    assert r.status_code == 200
    data = r.json()
    # 草稿题不可判分：即使选对也不计分，且不泄露答案
    assert data["score"] == 0
    assert data["answers"][0]["is_correct"] is False
    assert "correct_answer_text" not in data["answers"][0]


def test_list_bank_questions_published_only(client, setup_db):
    h, bank_id, qid = _seed_bank_with_question(status="published")
    r = client.get(f"/api/banks/{bank_id}/questions", headers=h)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["id"] == qid
    assert items[0]["options"] == [{"label": "2", "value": 0}, {"label": "1", "value": 1}]
