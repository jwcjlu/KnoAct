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
