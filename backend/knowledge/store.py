"""The FAQ set: the bundled knowledge_base files, overridden or extended by rows saved from the admin page.

Admin edits live in the database because a serverless host has a read-only disk and several instances.
"""
import json
import re
from pathlib import Path

from sqlalchemy import func, select

from backend.core.config import settings
from backend.database.database import SessionLocal, engine
from backend.database.models import FAQRow, now
from backend.knowledge.loader import FAQ

_ready = False


def number(faq_id: str) -> int:
    return int(re.sub(r"\D", "", faq_id) or 0)


def _ensure_table():
    global _ready
    if not _ready:
        FAQRow.__table__.create(engine, checkfirst=True)
        _ready = True


def _file_rows() -> dict[str, dict]:
    rows = {}
    for path in sorted(Path(settings.knowledge_dir).rglob("faq_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rows[data["id"]] = data
    return rows


def all_faqs() -> list[dict]:
    """Every FAQ, inactive ones included, in id order. A saved row replaces the file row with the same id."""
    _ensure_table()
    with SessionLocal() as db:
        saved = {row.id: row.as_dict() for row in db.scalars(select(FAQRow))}
    return sorted({**_file_rows(), **saved}.values(), key=lambda d: number(d["id"]))


def active_faqs() -> list[FAQ]:
    return [FAQ(id=d["id"], question=d["question"], answer=d["answer"], category=d.get("category", ""),
                keywords=d.get("keywords", []), data_as_of=d.get("data_as_of"), phase=d.get("phase", 1))
            for d in all_faqs() if d.get("active", True)]


def stamp() -> str:
    """Changes whenever an FAQ is saved, so an instance can tell that another one edited the set."""
    _ensure_table()
    with SessionLocal() as db:
        count, newest = db.execute(select(func.count(FAQRow.id), func.max(FAQRow.updated_at))).one()
    return f"{count}:{newest}"


def save_faq(data: dict) -> None:
    _ensure_table()
    with SessionLocal() as db:
        row = db.get(FAQRow, data["id"]) or FAQRow(id=data["id"])
        row.question, row.answer = data["question"], data["answer"]
        row.category = data.get("category", "")
        row.keywords = json.dumps(data.get("keywords", []), ensure_ascii=False)
        row.active = data.get("active", True)
        row.data_as_of = data.get("data_as_of")
        row.phase = data.get("phase", 2)
        row.updated_at = now()
        db.add(row)
        db.commit()
