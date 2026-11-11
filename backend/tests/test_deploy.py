from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from backend.core.config import normalize_database_url
from backend.database.database import SessionLocal
from backend.database.models import ChatSession, now
from backend.main import app

CONTACT = {"name": "Sam Lee", "email": "sam@example.com", "phone": "+44 20 7946 0958"}
CRON = {"Authorization": "Bearer test-cron"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("url,expected", [
    ("postgres://u:p@host:6543/db", "postgresql+psycopg2://u:p@host:6543/db"),
    ("postgresql://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),
    ("postgresql+psycopg2://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),
    ("sqlite:///chatbot.db", "sqlite:///chatbot.db"),
])
def test_database_url_names_the_postgres_driver(url, expected):
    assert normalize_database_url(url) == expected


def test_purge_endpoint_rejects_missing_or_wrong_secret(client):
    assert client.get("/api/internal/purge").status_code == 401
    assert client.get("/api/internal/purge", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/internal/purge", headers={"Authorization": "test-cron"}).status_code == 401


def test_purge_endpoint_deletes_expired_sessions_only(client):
    old = client.post("/api/session", json=CONTACT).json()["session_id"]
    recent = client.post("/api/session", json=CONTACT).json()["session_id"]
    with SessionLocal() as db:
        db.get(ChatSession, old).last_activity = now() - timedelta(days=31)
        db.commit()
    r = client.get("/api/internal/purge", headers=CRON)
    assert r.status_code == 200 and r.json()["deleted_sessions"] >= 1
    with SessionLocal() as db:
        assert db.get(ChatSession, old) is None
        assert db.get(ChatSession, recent) is not None
