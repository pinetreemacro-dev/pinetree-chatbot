import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.database import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id():
    return uuid.uuid4().hex


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ChatSession(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=now)
    contact = relationship("Contact")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    sender: Mapped[str] = mapped_column(String(10))  # user | bot
    text: Mapped[str] = mapped_column(Text)
    matched_faq: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Escalation(Base):
    __tablename__ = "escalations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class FAQRow(Base):
    """An FAQ added or edited in the admin page. It overrides the bundled knowledge_base file with the same id."""
    __tablename__ = "faqs"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), default="")
    keywords: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    data_as_of: Mapped[str | None] = mapped_column(String(10), nullable=True)
    phase: Mapped[int] = mapped_column(Integer, default=2)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    def as_dict(self) -> dict:
        data = {"id": self.id, "question": self.question, "answer": self.answer, "category": self.category,
                "keywords": json.loads(self.keywords or "[]"), "active": self.active}
        if self.data_as_of:
            data["data_as_of"] = self.data_as_of
        return data | {"phase": self.phase}


class RateHit(Base):
    """Request counter per client and time window, kept in the database so every server instance sees it."""
    __tablename__ = "rate_hits"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)  # scope:client:window
    count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
