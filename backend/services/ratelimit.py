import time

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.database.database import get_db
from backend.database.models import RateHit


def client_ip(request: Request) -> str:
    # Vercel sets x-forwarded-for itself; anywhere else a visitor could forge the header, so it is ignored.
    if settings.serverless:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


def _count(db: Session, key: str) -> int:
    bump = update(RateHit).where(RateHit.key == key).values(count=RateHit.count + 1)
    if db.execute(bump).rowcount == 0:
        try:
            db.add(RateHit(key=key, count=1))
            db.flush()
        except IntegrityError:  # a parallel request created the row first
            db.rollback()
            db.execute(bump)
    db.commit()
    return db.scalar(select(RateHit.count).where(RateHit.key == key))


def rate_limit(scope: str, setting: str, window_seconds: int):
    """Dependency that answers 429 once a visitor passes the limit in `settings.<setting>` for the time window.

    A limit of 0 turns it off. Counters live in the database, so every server instance shares them.
    """
    def check(request: Request, db: Session = Depends(get_db)):
        limit = getattr(settings, setting)
        if limit <= 0:
            return
        key = f"{scope}:{client_ip(request)}:{int(time.time() // window_seconds)}"
        if _count(db, key) > limit:
            raise HTTPException(429, "Too many requests. Please wait a little and try again.",
                                headers={"Retry-After": str(window_seconds)})
    return check
