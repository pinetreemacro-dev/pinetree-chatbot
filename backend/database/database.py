from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from backend.core.config import settings


def _foreign_keys_on(dbapi_connection, _record):
    # SQLite ignores foreign keys unless asked; Postgres always enforces them, so match it for local runs and tests.
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


if settings.database_url.startswith("sqlite"):
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _foreign_keys_on)
elif settings.serverless:
    # Instances come and go, so hold no connections of our own; Supabase's pooler (port 6543) owns them.
    engine = create_engine(settings.database_url, poolclass=NullPool, pool_pre_ping=True)
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
