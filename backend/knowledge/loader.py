import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FAQ:
    id: str
    question: str
    answer: str
    category: str = ""
    keywords: list[str] = field(default_factory=list)
    data_as_of: str | None = None
    phase: int = 1


def load_conversation(directory: Path) -> dict[str, str]:
    path = Path(directory) / "conversation" / "generic.json"
    return {item["question"]: item["answer"] for item in json.loads(path.read_text(encoding="utf-8"))} if path.exists() else {}


def load_related(directory: Path) -> dict[str, list[str]]:
    path = Path(directory) / "conversation" / "related.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_escalation_examples(directory: Path) -> list[str]:
    path = Path(directory) / "conversation" / "escalation_examples.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def load_faqs(directory: Path) -> list[FAQ]:
    faqs = []
    for path in sorted(Path(directory).rglob("faq_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get("active", True):
            continue
        faqs.append(FAQ(
            id=data["id"],
            question=data["question"],
            answer=data["answer"],
            category=data.get("category", ""),
            keywords=data.get("keywords", []),
            data_as_of=data.get("data_as_of"),
            phase=data.get("phase", 1),
        ))
    return faqs
