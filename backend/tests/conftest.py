import os
import shutil
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
_root = Path(__file__).resolve().parents[2]
shutil.copytree(_root / "knowledge_base", Path(_tmp) / "kb")

os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["KNOWLEDGE_DIR"] = str(Path(_tmp) / "kb")
os.environ["SMTP_HOST"] = ""
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-pass"
os.environ["CRON_SECRET"] = "test-cron"
# The suite opens many sessions from one address; the rate-limit tests switch the limits on themselves.
for _name in ("RATE_SESSION_PER_HOUR", "RATE_CONTACT_PER_HOUR", "RATE_CHAT_PER_MINUTE"):
    os.environ[_name] = "0"
