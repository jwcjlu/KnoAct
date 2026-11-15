from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Question, QuestionBank
from app.core.source_adapter import QuestionDraft
from conftest import auth_headers, make_account

client = TestClient(app)


class _FakeXkb:
    def configured(self):
        return True

    def fetch_by_knowledge(self, **kwargs):
        return {"data": [{"_": 1}], "errorCode": "0", "dataCount": 9}

    def normalize(self, raw):
        return [
            QuestionDraft(
                qtype="single_choice",
                question='如图<br/><img src="https://img.cuotixue.com/a.jpg">',
                options=[{"label": "A", "value": 0}],
                answer="A",
                tags={"source": "xuekubao", "subject_name": "数学"},
            ),
            QuestionDraft(
                qtype="fill_blank",
                question="填空题干",
                answer="1",
                tags={"subject_name": "数学"},
            ),
        ]


def _math_bank_headers():
    db = SessionLocal()
    p = make_account(db, "xkb_prev_parent", "parent")
    bank = QuestionBank(user_id=p.id, title="数学练习", subject="数学", source="manual")
    db.add(bank)
    db.commit()
    bid, h = bank.id, auth_headers(p)
    db.close()
    return h, bid


def test_preview_xuekubao_returns_drafts_without_persist(client, setup_db, monkeypatch):
    import app.routers.bank as bank_mod
    monkeypatch.setattr(bank_mod, "xuekubao_adapter", lambda db: _FakeXkb())
    h, bid = _math_bank_headers()
    before = SessionLocal().query(Question).count()
    r = client.post(
        f"/api/banks/{bid}/preview-xuekubao",
        headers=h,
        json={"knowledge_id": "15190", "page": 1, "max_import": 20},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["drafts"]) == 2
    assert data["drafts"][0]["question"].startswith("如图")
    assert data["page"] == 1
    assert data.get("data_count") == 9
    db = SessionLocal()
    assert db.query(Question).count() == before
    db.close()


def test_preview_xuekubao_subject_mismatch_400(client, setup_db, monkeypatch):
    import app.routers.bank as bank_mod

    class _Wrong(_FakeXkb):
        def normalize(self, raw):
            return [QuestionDraft(qtype="short_answer", question="语文题", tags={"subject_name": "语文"})]

    monkeypatch.setattr(bank_mod, "xuekubao_adapter", lambda db: _Wrong())
    h, bid = _math_bank_headers()
    r = client.post(
        f"/api/banks/{bid}/preview-xuekubao",
        headers=h,
        json={"knowledge_id": "1", "page": 1},
    )
    assert r.status_code == 400