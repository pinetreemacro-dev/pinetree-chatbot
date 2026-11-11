import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.security import require_admin
from backend.database.database import get_db
from backend.database.models import ChatSession, Contact, Escalation, Message

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


class FAQIn(BaseModel):
    question: str = Field(min_length=3, max_length=500, pattern=r"\S")
    answer: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    category: str = Field(default="", max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    active: bool = True
    data_as_of: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class StatusIn(BaseModel):
    status: Literal["open", "resolved"]


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    count = lambda q: db.scalar(q) or 0  # noqa: E731
    top = db.execute(
        select(Message.matched_faq, func.count()).where(Message.matched_faq.is_not(None))
        .group_by(Message.matched_faq).order_by(func.count().desc()).limit(5)).all()
    return {
        "conversations": count(select(func.count(ChatSession.id))),
        "leads": count(select(func.count(Contact.id))),
        "answered": count(select(func.count(Message.id)).where(Message.matched_faq.is_not(None))),
        "escalations_total": count(select(func.count(Escalation.id))),
        "escalations_open": count(select(func.count(Escalation.id)).where(Escalation.status == "open")),
        "top_faqs": [{"faq_id": f, "count": c} for f, c in top],
    }


@router.get("/leads")
def leads(db: Session = Depends(get_db)):
    rows = db.execute(
        select(ChatSession, Contact).join(Contact, Contact.id == ChatSession.contact_id)
        .order_by(ChatSession.last_activity.desc()).limit(500)).all()
    return [{"session_id": s.id, "name": c.name, "email": c.email, "phone": c.phone,
             "started_at": s.started_at.isoformat(), "last_activity": s.last_activity.isoformat()}
            for s, c in rows]


@router.get("/escalations")
def escalations(status: Literal["open", "resolved", "all"] = "all", db: Session = Depends(get_db)):
    q = (select(Escalation, ChatSession, Contact)
         .join(ChatSession, ChatSession.id == Escalation.session_id)
         .join(Contact, Contact.id == ChatSession.contact_id)
         .order_by(Escalation.created_at.desc()).limit(500))
    if status != "all":
        q = q.where(Escalation.status == status)
    return [{"id": e.id, "session_id": e.session_id, "question": e.question, "status": e.status,
             "email_sent": e.email_sent, "created_at": e.created_at.isoformat(),
             "name": c.name, "email": c.email, "phone": c.phone}
            for e, _, c in db.execute(q).all()]


@router.post("/escalations/{esc_id}/status")
def set_escalation_status(esc_id: int, body: StatusIn, db: Session = Depends(get_db)):
    esc = db.get(Escalation, esc_id)
    if esc is None:
        raise HTTPException(404, "Escalation not found")
    esc.status = body.status
    db.commit()
    return {"id": esc.id, "status": esc.status}


@router.get("/sessions/{session_id}/messages")
def transcript(session_id: str, db: Session = Depends(get_db)):
    msgs = db.scalars(select(Message).where(Message.session_id == session_id).order_by(Message.id)).all()
    return [{"sender": m.sender, "text": m.text, "faq_id": m.matched_faq,
             "confidence": m.confidence, "at": m.created_at.isoformat()} for m in msgs]


def _faq_paths():
    return {json.loads(p.read_text(encoding="utf-8"))["id"]: p
            for p in sorted(settings.knowledge_dir.rglob("faq_*.json"))}


@router.get("/faqs")
def list_faqs():
    return [json.loads(p.read_text(encoding="utf-8")) for p in _faq_paths().values()]


@router.post("/faqs")
def create_faq(body: FAQIn, request: Request):
    paths = _faq_paths()
    nums = [int(m.group(1)) for i in paths if (m := re.fullmatch(r"FAQ_(\d+)", i))]
    faq_id = f"FAQ_{max(nums, default=0) + 1:03d}"
    folder = settings.knowledge_dir / "phase_2"
    folder.mkdir(parents=True, exist_ok=True)
    return _write(request, folder / f"faq_{faq_id[4:]}.json", faq_id, body, phase=2)


@router.put("/faqs/{faq_id}")
def update_faq(faq_id: str, body: FAQIn, request: Request):
    path = _faq_paths().get(faq_id)
    if path is None:
        raise HTTPException(404, "FAQ not found")
    phase = json.loads(path.read_text(encoding="utf-8")).get("phase", 1)
    return _write(request, path, faq_id, body, phase)


def _write(request: Request, path, faq_id: str, body: FAQIn, phase: int):
    data = {"id": faq_id, **body.model_dump(exclude_none=True), "phase": phase}
    data["keywords"] = [k.strip() for k in body.keywords if k.strip()]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    request.app.state.engine.reload()
    return data
