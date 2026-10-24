def test_engine_connects():
    from app.database import engine
    with engine.connect() as conn:
        assert conn is not None

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
