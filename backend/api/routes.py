import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.chatbot.engine import contact_confirmation
from backend.core.config import settings
from backend.database.database import get_db
from backend.database.models import ChatSession, Contact, Escalation, Message, new_id, now
from backend.services.email import send_escalation_email
from backend.services.ratelimit import rate_limit

router = APIRouter(prefix="/api")


def check_phone(v: str) -> str:
    v = v.strip()
    if not re.fullmatch(r"\+?[\d\s\-()]{7,20}", v) or not 7 <= len(re.sub(r"\D", "", v)) <= 15:
        raise ValueError("Enter a valid phone number")
    return v


class SessionIn(BaseModel):
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    email: EmailStr
    phone: str
    returning: bool = False

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v):
        return check_phone(v)


class ChatIn(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=settings.max_message_length)


class ContactRequestIn(BaseModel):
    session_id: str
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    email: EmailStr
    phone: str
    message: str = Field(min_length=1, max_length=1000, pattern=r"\S")

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v):
        return check_phone(v)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/config")
def public_config():
    return {"contact_email": settings.contact_email}


@router.post("/session", dependencies=[Depends(rate_limit("session", "rate_session_per_hour", 3600))])
def create_session(body: SessionIn, request: Request, db: Session = Depends(get_db)):
    name = body.name.strip()
    contact = Contact(id=new_id(), name=name, email=body.email, phone=body.phone)
    session = ChatSession(id=new_id(), contact_id=contact.id)
    first_name = name.split()[0]
    greeting = (f"Welcome back, {first_name}! How can I help you today?" if body.returning
                else f"Hi, {first_name}! You're all set. How can I help you today?")
    db.add_all([contact, session])
    db.add(Message(session_id=session.id, sender="bot", text=greeting))
    db.commit()
    return {
        "session_id": session.id,
        "greeting": greeting,
        "suggested_questions": request.app.state.engine.sample_questions(),
    }


@router.post("/chat", dependencies=[Depends(rate_limit("chat", "rate_chat_per_minute", 60))])
def chat(body: ChatIn, background: BackgroundTasks, request: Request, db: Session = Depends(get_db)):
    session = db.get(ChatSession, body.session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    message = body.message.strip()
    asked_ids = set(db.scalars(select(Message.matched_faq).where(
        Message.session_id == session.id, Message.matched_faq.is_not(None))))
    request.app.state.engine.refresh_if_changed()
    reply = request.app.state.engine.answer(message, asked_ids=asked_ids)
    session.last_activity = now()
    db.add(Message(session_id=session.id, sender="user", text=message))
    db.add(Message(session_id=session.id, sender="bot", text=reply.text,
                   matched_faq=reply.faq_id, confidence=reply.confidence))
    if reply.escalated:
        db.add(Escalation(session_id=session.id, question=message, confidence=reply.confidence))
        history = [(m.sender, m.text) for m in db.scalars(
            select(Message).where(Message.session_id == session.id).order_by(Message.id))]
        contact = db.get(Contact, session.contact_id)
        background.add_task(_notify, session.id, contact.name, contact.email, contact.phone, message, history)
    db.commit()
    return {"answer": reply.text, "kind": reply.kind, "escalated": reply.escalated, "faq_id": reply.faq_id,
            "suggestions": reply.suggestions, "offer_contact": reply.offer_contact}


@router.post("/contact-request", dependencies=[Depends(rate_limit("contact", "rate_contact_per_hour", 3600))])
def contact_request(body: ContactRequestIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    session = db.get(ChatSession, body.session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    contact = db.get(Contact, session.contact_id)
    contact.name, contact.email, contact.phone = body.name.strip(), body.email, body.phone
    message = body.message.strip()
    confirmation = contact_confirmation(contact.name)
    session.last_activity = now()
    db.add(Message(session_id=session.id, sender="user", text=f"Message to the team: {message}"))
    db.add(Message(session_id=session.id, sender="bot", text=confirmation))
    question = f"Contact request: {message}"
    db.add(Escalation(session_id=session.id, question=question))
    history = [(m.sender, m.text) for m in db.scalars(
        select(Message).where(Message.session_id == session.id).order_by(Message.id))]
    background.add_task(_notify, session.id, contact.name, contact.email, contact.phone, question, history)
    db.commit()
    return {"answer": confirmation}


def _notify(session_id, name, email, phone, question, history):
    sent = send_escalation_email(name, email, phone, question, session_id, history)
    if sent:
        from backend.database.database import SessionLocal
        with SessionLocal() as db:
            for esc in db.scalars(select(Escalation).where(
                    Escalation.session_id == session_id, Escalation.question == question)):
                esc.email_sent = True
            db.commit()
