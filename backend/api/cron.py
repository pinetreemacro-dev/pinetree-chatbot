import secrets

from fastapi import APIRouter, Header, HTTPException

from backend.core.config import settings
from backend.services.retention import purge_old_data

router = APIRouter(prefix="/api/internal")


@router.get("/purge")
def purge(authorization: str = Header(default="")):
    """Run the 30-day purge on demand. A serverless host has no always-on scheduler, so its cron calls this
    (Vercel Cron sends `Authorization: Bearer $CRON_SECRET`)."""
    if not settings.cron_secret:
        raise HTTPException(503, "Scheduled purge is disabled. Set CRON_SECRET to enable it.")
    if not secrets.compare_digest(authorization.encode(), f"Bearer {settings.cron_secret}".encode()):
        raise HTTPException(401, "Invalid credentials")
    return {"deleted_sessions": purge_old_data()}
