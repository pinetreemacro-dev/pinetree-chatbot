from datetime import timedelta

from sqlalchemy import delete, select

from backend.core.config import settings
from backend.database.database import SessionLocal
from backend.database.models import ChatSession, Contact, Escalation, Message, RateHit, now


def purge_old_data() -> int:
    cutoff = now() - timedelta(days=settings.retention_days)
    with SessionLocal() as db:
        old = select(ChatSession.id).where(ChatSession.last_activity < cutoff)
        db.execute(delete(Message).where(Message.session_id.in_(old)))
        db.execute(delete(Escalation).where(Escalation.session_id.in_(old)))
        deleted = db.execute(delete(ChatSession).where(ChatSession.last_activity < cutoff)).rowcount
        used = select(ChatSession.contact_id)
        db.execute(delete(Contact).where(Contact.id.not_in(used)))
        db.execute(delete(RateHit).where(RateHit.created_at < now() - timedelta(days=1)))
        db.commit()
    return deleted
