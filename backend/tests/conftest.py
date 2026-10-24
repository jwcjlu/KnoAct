import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine, get_db, SessionLocal
from app.main import app

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()
