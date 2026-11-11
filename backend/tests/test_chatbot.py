from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from backend.database.database import SessionLocal
from backend.database.models import ChatSession, Escalation, Message, now
from backend.main import app
from backend.services.retention import purge_old_data

CONTACT = {"name": "Jane Doe", "email": "jane@example.com", "phone": "+91 98765 43210"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def start(client):
    r = client.post("/api/session", json=CONTACT)
    assert r.status_code == 200
    return r.json()["session_id"]


def ask(client, sid, text):
    return client.post("/api/chat", json={"session_id": sid, "message": text}).json()


def test_session_returns_personalized_greeting_and_suggestions(client):
    r = client.post("/api/session", json=CONTACT).json()
    assert r["greeting"] == "Hi, Jane! You're all set. How can I help you today?"
    assert len(r["suggested_questions"]) > 0


def test_returning_user_gets_welcome_back(client):
    r = client.post("/api/session", json={**CONTACT, "returning": True}).json()
    assert r["greeting"].startswith("Welcome back, Jane!")


def test_public_config_exposes_contact_email(client):
    assert client.get("/api/config").json()["contact_email"]


@pytest.mark.parametrize("bad", [
    {**CONTACT, "email": "nope"},
    {**CONTACT, "phone": "abc"},
    {**CONTACT, "name": " "},
])
def test_contact_validation(client, bad):
    assert client.post("/api/session", json=bad).status_code == 422


@pytest.mark.parametrize("question,expected", [
    ("Who is the auditor of the fund?", "Forvis Mazars"),
    ("What is the minimum initial investment?", "$100,000"),
    ("What is the redemption notice period?", "15 calendar days"),
    ("What is the fund's Sharpe Ratio?", "1.22"),
])
def test_answers_known_questions(client, question, expected):
    r = ask(client, start(client), question)
    assert r["kind"] == "answer" and expected in r["answer"]


def test_period_guard_never_mixes_up_return_periods(client):
    r = ask(client, start(client), "What has the fund returned over the last two years?")
    assert "64.92%" in r["answer"] and "93.95%" not in r["answer"]


def test_ambiguous_question_asks_for_clarification_with_suggestions(client):
    r = ask(client, start(client), "What's the return?")
    assert r["kind"] == "clarify" and not r["escalated"] and len(r["suggestions"]) >= 1


def test_forward_looking_questions_are_handed_to_the_team(client):
    sid = start(client)
    for q in ["What will the fund return next year?", "Can you guarantee my returns?", "Should I invest in this fund?"]:
        r = ask(client, sid, q)
        assert r["escalated"] and "In the meantime" in r["answer"]


def test_dated_answers_carry_date(client):
    r = ask(client, start(client), "What was the fund's 12-month return?")
    assert "27.29%" in r["answer"] and "2026-06-30" in r["answer"]


def test_out_of_scope_escalates(client):
    sid = start(client)
    r = ask(client, sid, "What is the weather in Paris tomorrow?")
    assert r["escalated"] and "team" in r["answer"]
    with SessionLocal() as db:
        assert db.query(Escalation).filter_by(session_id=sid).count() == 1


def test_small_talk_does_not_escalate(client):
    assert not ask(client, start(client), "hello")["escalated"]


def test_unknown_session_404(client):
    assert client.post("/api/chat", json={"session_id": "x", "message": "hi"}).status_code == 404


def test_message_length_limit(client):
    assert client.post("/api/chat", json={"session_id": start(client), "message": "a" * 501}).status_code == 422


def test_retention_purges_old_sessions(client):
    sid = start(client)
    ask(client, sid, "What is the weather in Paris tomorrow?")
    with SessionLocal() as db:
        db.get(ChatSession, sid).last_activity = now() - timedelta(days=31)
        db.commit()
    purge_old_data()
    with SessionLocal() as db:
        assert db.get(ChatSession, sid) is None
        assert db.query(Message).filter_by(session_id=sid).count() == 0
        assert db.query(Escalation).filter_by(session_id=sid).count() == 0


HANDOFF = ("I'm connecting you with our team, who will get in touch with you shortly. "
           "In the meantime, please feel free to ask any other questions you may have.")


def test_handoff_uses_the_approved_wording_and_offers_the_contact_button(client):
    r = ask(client, start(client), "What will the fund return next year?")
    assert r["answer"] == HANDOFF and r["offer_contact"] and r["kind"] == "escalate"


def test_asking_for_a_person_offers_the_contact_button_without_a_handoff_record(client):
    sid = start(client)
    r = ask(client, sid, "I want to talk to a person")
    assert r["kind"] == "contact" and r["offer_contact"] and "info@pinetreemacro.com" in r["answer"]
    assert "24 to 48 hours" in r["answer"]
    with SessionLocal() as db:
        assert db.query(Escalation).filter_by(session_id=sid).count() == 0


def test_contact_the_team_answer_offers_the_button(client):
    r = ask(client, start(client), "How can I contact the team?")
    assert r["kind"] == "answer" and r["offer_contact"]
    assert "info@pinetreemacro.com" in r["answer"] and "Lord Sinha Road" in r["answer"]


def test_every_answer_suggests_related_questions(client):
    r = ask(client, start(client), "What is the performance fee structure?")
    assert r["suggestions"] == ["What is the hurdle rate?", "What is a high watermark?", "What is the management fee?"]


def test_approved_performance_fee_answer(client):
    r = ask(client, start(client), "How does the performance fee work?")
    assert r["answer"] == ("The fund charges a 15% performance fee on returns above a 7% hurdle rate, subject to a high watermark. "
                           "For any further performance fee query please feel free to contact our team.")


def test_other_team_members_and_services_are_handed_to_the_team(client):
    sid = start(client)
    for q in ["Who is on the PineTree Macro team?", "What research does PineTree Macro publish?"]:
        assert ask(client, sid, q)["escalated"], q
    founder = ask(client, sid, "Who is Ritesh Jain?")["answer"]
    assert "Founder" in founder and "LinkedIn" not in founder


def test_contact_request_is_saved_for_the_admin_and_confirmed(client):
    sid = start(client)
    body = {"session_id": sid, "name": "Jane Doe", "email": "jane.new@example.com", "phone": "+91 91111 22222",
            "message": "Please call me about onboarding."}
    r = client.post("/api/contact-request", json=body)
    assert r.status_code == 200 and "Thank you, Jane." in r.json()["answer"] and "24 to 48 hours" in r.json()["answer"]
    with SessionLocal() as db:
        esc = db.query(Escalation).filter_by(session_id=sid).one()
        assert esc.question == "Contact request: Please call me about onboarding."
        contact = db.get(ChatSession, sid).contact
        assert contact.email == "jane.new@example.com" and contact.phone == "+91 91111 22222"
        texts = [m.text for m in db.query(Message).filter_by(session_id=sid)]
        assert "Message to the team: Please call me about onboarding." in texts


@pytest.mark.parametrize("change", [{"message": "  "}, {"email": "nope"}, {"phone": "abc"}, {"name": " "}, {"message": "x" * 1001}])
def test_contact_request_validation(client, change):
    body = {"session_id": start(client), "name": "Jane Doe", "email": "jane@example.com", "phone": "+91 91111 22222",
            "message": "Hello", **change}
    assert client.post("/api/contact-request", json=body).status_code == 422


def test_contact_request_unknown_session(client):
    body = {"session_id": "nope", "name": "A", "email": "a@example.com", "phone": "+91 91111 22222", "message": "Hi"}
    assert client.post("/api/contact-request", json=body).status_code == 404
