from app.database import SessionLocal


def test_turn_table_exists(setup_db):
    from app.models import Turn, ToolCall
    db = SessionLocal()
    turn = Turn(user_id=1, lesson_id=1, capability="chat", mode="chat",
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
    r = client.post("/api/ask", json={"lesson_id": 1, "question": "你好", "context": "白鹭是一首精巧的诗"})
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
    r = client.post("/api/ask", json={"lesson_id": 1, "question": "唯一标记问题", "context": ""})
    assert r.status_code == 200
    db = SessionLocal()
    turn = db.query(Turn).filter_by(question="唯一标记问题").order_by(Turn.id.desc()).first()
    assert turn is not None
    assert turn.mode == "chat"
    assert turn.final_answer != ""          # _persist 写入了答案
    assert turn.status in ("done", "error")  # _persist 写入了状态
    db.close()
