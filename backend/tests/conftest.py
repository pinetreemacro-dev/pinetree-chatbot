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
