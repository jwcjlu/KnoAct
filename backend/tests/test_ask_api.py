from app.database import SessionLocal
from conftest import make_account, make_lesson, bound_child_headers


def _h(uid):
    return bound_child_headers(uid)


def _seed_user_lesson():
    from app.models import UserDocument
    db = SessionLocal()
    p = make_account(db, "p_ask", "parent")
    uid = make_account(db, "k_ask", "child", parent=p).id
    lesson = make_lesson(db)
    lid = lesson.id
    db.add(UserDocument(user_id=uid, document_id=lesson.document_id))
    db.commit(); db.close()
    return uid, lid


def test_ask_req_accepts_sentences(setup_db):
    from app.routers.notes import AskReq
    req = AskReq(lesson_id=1, question="?", context="a。b。", sentences=["a。", "b。"])
    assert req.sentences == ["a。", "b。"]


def test_turn_table_exists(setup_db):
    from app.models import Turn, ToolCall
    uid, lid = _seed_user_lesson()
    db = SessionLocal()
    turn = Turn(user_id=uid, lesson_id=lid, capability="chat", mode="chat",
                question="你好", context="", status="done", final_answer="你好呀")
    db.add(turn); db.commit(); db.flush()
    assert turn.id is not None
    tc = ToolCall(turn_id=turn.id, step=1, tool_name="lookup_word",
                  args='{"word": "x"}', result='{"meaning": "m"}')
    db.add(tc); db.commit()
    assert db.query(ToolCall).count() == 1
    db.close()


from fastapi.testclient import TestClient
from app.main import app
from app.models import ModelConfig

client = TestClient(app)


def test_ask_api_end_to_end(setup_db):
    # 用 fake provider：不会返回合法 JSON，应走降级返回友好文案（status=error 但不 500）
    db = SessionLocal()
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit(); db.close()
    uid, lid = _seed_user_lesson()
    r = client.post("/api/ask", json={"lesson_id": lid, "question": "你好", "context": "白鹭是一首精巧的诗"},
                    headers=_h(uid))
    assert r.status_code == 200
    body = r.json()
    assert "answer" in body
    assert "citations" in body
    assert "mode" in body


def test_ask_api_persists_turn(setup_db):
    from app.models import Turn, ModelConfig
    db = SessionLocal()
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit(); db.close()
    uid, lid = _seed_user_lesson()
    r = client.post("/api/ask", json={"lesson_id": lid, "question": "唯一标记问题", "context": ""},
                    headers=_h(uid))
    assert r.status_code == 200
    db = SessionLocal()
    turn = db.query(Turn).filter_by(question="唯一标记问题").order_by(Turn.id.desc()).first()
    assert turn is not None
    assert turn.user_id == uid and turn.lesson_id == lid
    assert turn.mode == "chat"
    assert turn.final_answer != ""          # _persist 写入了答案
    assert turn.status in ("done", "error")  # _persist 写入了状态
    db.close()


from app.runtime.orchestrator import extract_citations, filter_citations


def test_filter_citations_removes_out_of_range():
    citations = [1, 5, 2]
    assert filter_citations(citations, 3) == [1, 2]


def test_filter_citations_no_filter_when_max_zero():
    citations = [1, 5, 2]
    assert filter_citations(citations, 0) == [1, 5, 2]


def test_extract_and_filter_roundtrip():
    answer = "答案……[第1句]……[第5句]……[第2句]"
    citations = extract_citations(answer)
    filtered = filter_citations(citations, 3)
    assert filtered == [1, 2]


def test_ask_stream_endpoint(setup_db):
    from app.models import ModelConfig
    db = SessionLocal()
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit(); db.close()
    uid, lid = _seed_user_lesson()
    r = client.post("/api/ask/stream", json={"lesson_id": lid, "question": "你好", "context": ""},
                    headers=_h(uid))
    assert r.status_code == 200
    body = r.text
    assert "data: " in body
    assert '"type": "final"' in body
    assert '"answer"' in body


def test_ask_stream_persists_turn(setup_db):
    from app.models import Turn, ModelConfig
    db = SessionLocal()
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit(); db.close()
    uid, lid = _seed_user_lesson()
    r = client.post("/api/ask/stream", json={"lesson_id": lid, "question": "流式问题", "context": ""},
                    headers=_h(uid))
    assert r.status_code == 200
    db = SessionLocal()
    turn = db.query(Turn).filter_by(question="流式问题").first()
    assert turn is not None
    assert turn.user_id == uid and turn.lesson_id == lid
    db.close()


def test_persist_turn_without_lesson_stores_null(setup_db):
    from app.models import Turn
    from app.core.context import UnifiedContext
    from app.runtime.orchestrator import persist_turn
    uid, _ = _seed_user_lesson()
    ctx = UnifiedContext(user_id=uid, lesson_id=0, question="无课程提问")
    persist_turn(ctx, "chat", "答案", [], [], {})
    db = SessionLocal()
    turn = db.query(Turn).filter_by(question="无课程提问").first()
    assert turn is not None and turn.lesson_id is None
    db.close()


def test_ask_stream_error_terminates(monkeypatch, setup_db):
    # 让 get_provider 返回一个 generate 会抛异常的 provider
    from app.models import ModelConfig
    db = SessionLocal()
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit(); db.close()
    import app.services.ai as ai
    class BoomProvider:
        name = "boom"
        model = ""
        api_key = ""
        def generate(self, prompt, system="", json_mode=False):
            raise RuntimeError("no key")
    monkeypatch.setattr(ai, "get_provider", lambda db: BoomProvider())
    uid, lid = _seed_user_lesson()
    r = client.post("/api/ask/stream", json={"lesson_id": lid, "question": "会失败", "context": ""},
                    headers=_h(uid))
    assert r.status_code == 200
    # 流必须终止（不会无限阻塞），且应含 error 事件
    assert '"type": "error"' in r.text
