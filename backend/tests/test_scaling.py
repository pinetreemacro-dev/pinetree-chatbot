"""Behaviour that has to hold when several server instances share one database."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.core.config import settings
from backend.knowledge import store
from backend.main import app

CONTACT = {"name": "Sam Lee", "email": "sam@example.com", "phone": "+44 20 7946 0958"}
ADMIN = ("admin", "test-pass")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def session(client, **headers):
    return client.post("/api/session", json=CONTACT, headers=headers)


def freeze_time(monkeypatch, seconds):
    monkeypatch.setattr("backend.services.ratelimit.time", SimpleNamespace(time=lambda: seconds))


def test_admin_faq_edits_are_saved_in_the_database_not_in_files(client):
    files = lambda: len(list(Path(settings.knowledge_dir).rglob("faq_*.json")))  # noqa: E731
    before = files()
    r = client.post("/api/admin/faqs", auth=ADMIN, json={
        "question": "Does the fund publish a yearly letter?", "answer": "Yes, every January.", "category": "Company"})
    assert r.status_code == 200
    assert files() == before
    assert any(f["id"] == r.json()["id"] and f["answer"] == "Yes, every January." for f in store.all_faqs())


def test_a_saved_faq_overrides_the_bundled_file_with_the_same_id(client):
    original = next(f for f in store.all_faqs() if f["id"] == "FAQ_015")
    try:
        r = client.put("/api/admin/faqs/FAQ_015", auth=ADMIN, json={
            "question": original["question"], "answer": "Changed in the admin page.",
            "category": original["category"], "keywords": original["keywords"]})
        assert r.status_code == 200 and r.json()["phase"] == original["phase"]
        assert next(f for f in store.all_faqs() if f["id"] == "FAQ_015")["answer"] == "Changed in the admin page."
    finally:
        client.put("/api/admin/faqs/FAQ_015", auth=ADMIN, json={
            k: original[k] for k in ("question", "answer", "category", "keywords")})


def test_another_instances_faq_change_is_picked_up_on_the_next_chat(client):
    q = "Does the fund hold an annual investor day?"
    sid = session(client).json()["session_id"]
    assert client.post("/api/chat", json={"session_id": sid, "message": q}).json()["kind"] != "answer"
    # Saved straight to the database, as a different server instance's admin page would do it.
    store.save_faq({"id": "FAQ_900", "question": q, "answer": "Yes, in March.", "category": "Company",
                    "keywords": [], "active": True, "phase": 2})
    reply = client.post("/api/chat", json={"session_id": sid, "message": q}).json()
    assert reply["kind"] == "answer" and reply["answer"] == "Yes, in March."


def test_session_creation_is_limited_per_visitor(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_session_per_hour", 2)
    freeze_time(monkeypatch, 1_000_000)
    assert [session(client).status_code for _ in range(3)] == [200, 200, 429]
    blocked = session(client)
    assert blocked.status_code == 429 and blocked.headers["retry-after"] == "3600"
    assert "too many requests" in blocked.json()["detail"].lower()
    freeze_time(monkeypatch, 1_000_000 + 3600)  # the next hour starts a fresh count
    assert session(client).status_code == 200


def test_chat_and_contact_requests_have_their_own_limits(client, monkeypatch):
    sid = session(client).json()["session_id"]
    monkeypatch.setattr(settings, "rate_chat_per_minute", 2)
    monkeypatch.setattr(settings, "rate_contact_per_hour", 1)
    freeze_time(monkeypatch, 2_000_000)
    chat = lambda: client.post("/api/chat", json={"session_id": sid, "message": "hello"}).status_code  # noqa: E731
    assert [chat() for _ in range(3)] == [200, 200, 429]
    contact = lambda: client.post("/api/contact-request", json={  # noqa: E731
        "session_id": sid, **CONTACT, "message": "Please call me"}).status_code
    assert [contact(), contact()] == [200, 429]


def test_forwarded_address_is_trusted_only_on_a_serverless_host(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_session_per_hour", 1)
    freeze_time(monkeypatch, 3_000_000)
    # Locally the header could be forged, so both requests count against the same address.
    assert [session(client, **{"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in (1, 2)] == [200, 429]
    freeze_time(monkeypatch, 4_000_000)
    monkeypatch.setattr(settings, "serverless", True)
    codes = [session(client, **{"X-Forwarded-For": ip}).status_code for ip in ("10.0.0.1", "10.0.0.2", "10.0.0.1")]
    assert codes == [200, 200, 429]
