import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def normalize_database_url(url: str) -> str:
    """Supabase and most hosts hand out postgres:// or postgresql://; SQLAlchemy needs the driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


class Settings:
    database_url = normalize_database_url(os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'chatbot.db'}"))
    # Vercel sets VERCEL on every deployment; serverless instances have no always-on scheduler or writable disk.
    serverless = bool(os.getenv("VERCEL"))
    cron_secret = os.getenv("CRON_SECRET", "")
    escalation_email = os.getenv("ESCALATION_EMAIL", "info@pinetreemacro.com")
    contact_email = os.getenv("CONTACT_EMAIL", "") or os.getenv("ESCALATION_EMAIL", "info@pinetreemacro.com")
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    # Cosine similarities from the embedding model (not probabilities); calibrated on the 223-question test set.
    confidence_high = float(os.getenv("CONFIDENCE_HIGH", "0.90"))
    confidence_low = float(os.getenv("CONFIDENCE_LOW", "0.74"))
    clarify_margin = float(os.getenv("CLARIFY_MARGIN", "0.04"))
    escalation_example_similarity = float(os.getenv("ESCALATION_EXAMPLE_SIMILARITY", "0.85"))
    embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    model_cache_dir = Path(os.getenv("MODEL_CACHE_DIR", str(ROOT / ".cache" / "fastembed")))
    retention_days = int(os.getenv("RETENTION_DAYS", "30"))
    allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")]
    knowledge_dir = Path(os.getenv("KNOWLEDGE_DIR", str(ROOT / "knowledge_base")))
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    frontend_dir = ROOT / "frontend"
    max_message_length = 500


settings = Settings()
