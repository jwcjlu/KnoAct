from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import ModelConfig, ModelConnection, ModelProfile, RoleBinding
from app.routers.config_router import router as config_router


def _client():
    app = FastAPI()
    app.include_router(config_router)
    return TestClient(app)


def _clear(db):
    for m in (RoleBinding, ModelProfile, ModelConnection, ModelConfig):
        db.query(m).delete()
    db.commit()


def test_get_catalog_lists_all_roles_and_registry(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    body = c.get("/api/config/catalog").json()
    assert set(body["services"].keys()) == {
        "llm", "task", "embedding", "search", "tts", "stt", "imagegen"
    }
    assert "registry" in body
    assert "connections" in body


def test_put_catalog_persists_connection_and_binding(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    payload = {
        "connections": [
            {"id": None, "provider": "openai", "name": "中转站",
             "base_url": "https://x/v1", "api_key": "sk-real"}
        ],
        "services": {
            "llm": {"profile_id": None, "connection_id": None,
                    "connection_index": 0, "model": "gpt-4o", "options": "{}",
                    "mode": "inherit"},
        },
    }
    assert c.put("/api/config/catalog", json=payload).json()["ok"] is True

    body = c.get("/api/config/catalog").json()
    assert body["connections"][0]["name"] == "中转站"
    assert body["connections"][0]["api_key"] == "***"
    assert body["services"]["llm"]["model"] == "gpt-4o"

    db = SessionLocal()
    assert db.query(ModelConnection).count() == 1
    assert db.query(ModelProfile).count() == 1
    assert db.query(RoleBinding).filter_by(role="llm").count() == 1
    db.close()


def test_put_catalog_does_not_clobber_masked_key(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    first = {
        "connections": [{"id": None, "provider": "deepseek", "name": "ds",
                         "base_url": "", "api_key": "sk-original"}],
        "services": {"llm": {"connection_index": 0, "model": "deepseek-chat",
                             "options": "{}", "mode": "inherit"}},
    }
    c.put("/api/config/catalog", json=first)
    got = c.get("/api/config/catalog").json()

    # 原样回传（key 是 MASK），不应把真 key 覆盖成 ***
    second = {"connections": got["connections"], "services": got["services"]}
    c.put("/api/config/catalog", json=second)

    db = SessionLocal()
    assert db.query(ModelConnection).first().api_key == "sk-original"
    db.close()


def test_deleting_connection_nulls_profile_reference(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    c.put("/api/config/catalog", json={
        "connections": [{"id": None, "provider": "openai", "name": "a",
                         "base_url": "https://x/v1", "api_key": "k"}],
        "services": {"llm": {"connection_index": 0, "model": "gpt-4o",
                             "options": "{}", "mode": "inherit"}},
    })
    got = c.get("/api/config/catalog").json()
    c.put("/api/config/catalog", json={
        "connections": [],
        "services": got["services"],
    })
    db = SessionLocal()
    prof = db.query(ModelProfile).filter_by(role="llm").first()
    assert prof is not None
    assert prof.connection_id is None
    db.close()
