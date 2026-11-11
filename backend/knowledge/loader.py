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
