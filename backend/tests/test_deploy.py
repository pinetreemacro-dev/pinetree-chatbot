import tomllib
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.core.config import normalize_database_url
from backend.database.database import SessionLocal
from backend.database.models import ChatSession, Message, now
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


def test_local_database_enforces_foreign_keys_like_postgres():
    with SessionLocal() as db:
        db.add(Message(session_id="no-such-session", sender="bot", text="x"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_vercel_entry_point_is_configured_and_importable():
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["vercel"]["entrypoint"] == "index:app"
    import index
    assert index.app is app


def test_pyproject_and_requirements_list_the_same_packages():
    root = Path(__file__).resolve().parents[2]
    declared = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    pinned = [line.strip() for line in (root / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.startswith("#")]
    assert sorted(declared) == sorted(pinned)


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
