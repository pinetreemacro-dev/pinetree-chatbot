import pytest
from fastapi.testclient import TestClient

from backend.main import app

AUTH = ("admin", "test-pass")
CONTACT = {"name": "Sam Lee", "email": "sam@example.com", "phone": "+44 20 7946 0958"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_admin_requires_credentials(client):
    assert client.get("/api/admin/stats").status_code == 401
    assert client.get("/admin").status_code == 401
    assert client.get("/api/admin/stats", auth=("admin", "wrong")).status_code == 401


def test_admin_page_and_public_pages_load(client):
    assert client.get("/admin", auth=AUTH).status_code == 200
    assert "PineTree Assistant" in client.get("/").text
    assert client.get("/static/chat.js").status_code == 200
    for path in ("/", "/static/chat.js", "/static/chat.css"):
        assert client.get(path).headers["cache-control"] == "no-cache"


def test_escalation_flow_visible_in_admin(client):
    sid = client.post("/api/session", json=CONTACT).json()["session_id"]
    client.post("/api/chat", json={"session_id": sid, "message": "Do you offer mortgages in Mars?"})

    esc = [e for e in client.get("/api/admin/escalations", auth=AUTH).json() if e["session_id"] == sid]
    assert len(esc) == 1 and esc[0]["status"] == "open" and esc[0]["email"] == "sam@example.com"

    r = client.post(f"/api/admin/escalations/{esc[0]['id']}/status", json={"status": "resolved"}, auth=AUTH)
    assert r.json()["status"] == "resolved"
    assert client.post("/api/admin/escalations/999999/status", json={"status": "open"}, auth=AUTH).status_code == 404
    assert client.post(f"/api/admin/escalations/{esc[0]['id']}/status", json={"status": "bogus"}, auth=AUTH).status_code == 422

    msgs = client.get(f"/api/admin/sessions/{sid}/messages", auth=AUTH).json()
    assert [m["sender"] for m in msgs] == ["bot", "user", "bot"]
    assert any(l["session_id"] == sid for l in client.get("/api/admin/leads", auth=AUTH).json())
    assert client.get("/api/admin/stats", auth=AUTH).json()["escalations_total"] >= 1


def test_new_faq_is_immediately_answerable(client):
    q = "Does the fund have a mobile app for investors?"
    sid = client.post("/api/session", json=CONTACT).json()["session_id"]
    assert client.post("/api/chat", json={"session_id": sid, "message": q}).json()["kind"] != "answer"

    existing = [int(f["id"][4:]) for f in client.get("/api/admin/faqs", auth=AUTH).json()]
    r = client.post("/api/admin/faqs", auth=AUTH, json={
        "question": q, "answer": "Yes, every quarter.", "category": "Company", "keywords": ["newsletter"]})
    assert r.status_code == 200 and r.json()["id"] == f"FAQ_{max(existing) + 1:03d}"

    reply = client.post("/api/chat", json={"session_id": sid, "message": q}).json()
    assert not reply["escalated"] and reply["answer"] == "Yes, every quarter."


def test_edit_and_deactivate_faq(client):
    faqs = {f["id"]: f for f in client.get("/api/admin/faqs", auth=AUTH).json()}
    f = faqs["FAQ_006"]
    body = {k: f[k] for k in ("question", "answer", "category", "keywords")} | {"active": False}
    assert client.put("/api/admin/faqs/FAQ_006", json=body, auth=AUTH).status_code == 200
    try:
        sid = client.post("/api/session", json=CONTACT).json()["session_id"]
        assert client.post("/api/chat", json={"session_id": sid, "message": "Who is the fund's auditor?"}).json()["faq_id"] != "FAQ_006"
    finally:
        client.put("/api/admin/faqs/FAQ_006", json={**body, "active": True}, auth=AUTH)
    assert client.put("/api/admin/faqs/FAQ_999", json=body, auth=AUTH).status_code == 404


def test_faq_validation(client):
    assert client.post("/api/admin/faqs", auth=AUTH, json={"question": " ", "answer": "x"}).status_code == 422
