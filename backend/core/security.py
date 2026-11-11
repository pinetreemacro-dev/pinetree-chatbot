import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from backend.core.config import settings

_basic = HTTPBasic()


def require_admin(creds: HTTPBasicCredentials = Depends(_basic)):
    if not settings.admin_password:
        raise HTTPException(503, "Admin is disabled. Set ADMIN_PASSWORD in .env to enable it.")
    user_ok = secrets.compare_digest(creds.username.encode(), settings.admin_username.encode())
    pass_ok = secrets.compare_digest(creds.password.encode(), settings.admin_password.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Basic"})
