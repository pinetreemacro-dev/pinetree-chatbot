from dataclasses import dataclass, field

import numpy as np

from backend.chatbot.guards import FORWARD_LOOKING, HUMAN_REQUEST, periods
from backend.core.config import settings
from backend.knowledge import store
from backend.knowledge.loader import load_conversation, load_escalation_examples, load_related
from backend.knowledge.retrieval import SemanticIndex, normalize

ESCALATION_REPLY = ("I'm connecting you with our team, who will get in touch with you shortly. "
                    "In the meantime, please feel free to ask any other questions you may have.")
CLARIFY_REPLY = "I want to make sure I give you the right answer. Did you mean one of these?"
CONTACT_CATEGORY = "Contact the Team"
TEAM_HOURS = "Monday to Friday, 10am to 6pm IST"
REPLY_WINDOW = "24 to 48 hours on working days"
EXACT_MATCH = 0.985


def contact_reply() -> str:
    return (f"Of course. Use the Contact our team button to send a message, or write to {settings.contact_email}. "
            f"Our team is available {TEAM_HOURS}, and you can expect a reply within {REPLY_WINDOW}.")


def contact_confirmation(name: str) -> str:
    return (f"Thank you, {name.split()[0]}. Your message has been sent to our team. "
            f"You can expect a reply within {REPLY_WINDOW} ({TEAM_HOURS}).")


@dataclass
class Reply:
    text: str
    kind: str = "answer"  # answer | clarify | escalate | contact | generic
    faq_id: str | None = None
    confidence: float | None = None
    suggestions: list[str] = field(default_factory=list)
    offer_contact: bool = False

    @property
    def escalated(self) -> bool:
        return self.kind == "escalate"


class ChatEngine:
    def __init__(self):
        self.reload()

    def reload(self):
        stamp = store.stamp()
        faqs = store.active_faqs()
        generic = {normalize(q): a for q, a in load_conversation(settings.knowledge_dir).items()}
        related_map = load_related(settings.knowledge_dir)
        index = SemanticIndex(faqs, load_escalation_examples(settings.knowledge_dir))
        # Rows that share an answer are one topic: the first row is its anchor, and the first properly written
        # question (capitalised, ending in ? or .) is the wording shown in suggestions, never a typo variant.
        canonical, display = {}, {}
        for faq in faqs:
            canonical.setdefault(faq.answer, faq)
            if faq.question[:1].isupper() and faq.question.rstrip()[-1:] in "?.":
                display.setdefault(faq.answer, faq.question)
        # Assigned together at the end so a request running meanwhile never sees half old, half new state.
        self.generic, self.related_map, self.index = generic, related_map, index
        self.by_id = {f.id: f for f in faqs}
        self.by_question = {normalize(f.question): f for f in faqs}
        self.position = {f.id: i for i, f in enumerate(faqs)}
        self.canonical, self.display = canonical, display
        self.faqs, self.stamp = faqs, stamp

    def refresh_if_changed(self):
        """Another server instance may have saved an FAQ from the admin page; pick that up."""
        if store.stamp() != self.stamp:
            self.reload()

    def sample_questions(self, n: int = 6) -> list[str]:
        pool = [f for f in self.faqs if f.phase == 1] or self.faqs
        step = max(1, len(pool) // n)
        return [f.question for f in pool[::step][:n]]

    def answer(self, message: str, asked_ids=frozenset(), _exclude_ids=frozenset(), _exclude_examples=frozenset()) -> Reply:
        """Infer intent, never invent facts: answer only when confident, otherwise clarify or hand off.

        The underscore arguments exist so tests can hold a question out of the index.
        """
        generic = self.generic.get(normalize(message))
        if generic is not None:
            return Reply(generic, kind="generic", suggestions=self.sample_questions(3))
        if FORWARD_LOOKING.search(message) or not self.faqs:
            return self._handoff()

        scores, vector = self.index.scores(message)
        for i, faq in enumerate(self.faqs):
            if faq.id in _exclude_ids:
                scores[i] = -1.0
        asked = periods(message)
        if asked:
            for i, faq_periods in enumerate(self.index.periods):
                if faq_periods and not (asked & faq_periods):
                    scores[i] = -1.0

        order = np.argsort(-scores)
        best = int(order[0])
        top = float(scores[best])
        faq = self.faqs[best]
        if top >= EXACT_MATCH:
            return self._answer(faq, top, asked_ids)

        if HUMAN_REQUEST.search(message):
            return Reply(contact_reply(), kind="contact", offer_contact=True, suggestions=self.sample_questions(3))

        example_scores = self.index.example_scores(vector).copy() if len(self.index.examples) else np.array([-1.0])
        for i in _exclude_examples:
            example_scores[i] = -1.0
        if float(example_scores.max()) >= max(top, settings.escalation_example_similarity) or top < settings.confidence_low:
            return self._handoff(top)

        distinct = []
        for i in order[:12]:
            candidate = self.faqs[int(i)]
            if float(scores[int(i)]) >= settings.confidence_low - 0.08 and all(candidate.answer != d.answer for d in distinct):
                distinct.append(candidate)
        runner_up = next((float(scores[int(i)]) for i in order[1:6] if self.faqs[int(i)].answer != faq.answer), -1.0)
        if top < settings.confidence_high or top - runner_up < settings.clarify_margin:
            shown = [self.display[d.answer] for d in distinct if d.answer in self.display]
            return Reply(CLARIFY_REPLY, kind="clarify", confidence=top, suggestions=shown[:3])
        return self._answer(faq, top, asked_ids)

    def _handoff(self, confidence=None) -> Reply:
        return Reply(ESCALATION_REPLY, kind="escalate", confidence=confidence, offer_contact=True,
                     suggestions=self.sample_questions(3))

    def _answer(self, faq, confidence: float, asked_ids) -> Reply:
        text = faq.answer
        if faq.data_as_of:
            text += f" (Data as of {faq.data_as_of}.)"
        return Reply(text, faq_id=faq.id, confidence=confidence, suggestions=self.related(faq, asked_ids),
                     offer_contact=faq.category == CONTACT_CATEGORY)

    def related(self, faq, asked_ids=frozenset(), count: int = 3) -> list[str]:
        """Follow-up questions: hand-picked ones first, then the nearest topics. Never repeats an answer already given."""
        seen = {faq.answer} | {self.by_id[i].answer for i in asked_ids if i in self.by_id}
        canonical = self.canonical[faq.answer]
        picks = []
        for question in self.related_map.get(canonical.id) or self.related_map.get(faq.id) or []:
            target = self.by_question.get(normalize(question))
            if len(picks) < count and not (target and target.answer in seen):
                picks.append(question)
                if target:
                    seen.add(target.answer)
        if len(picks) < count:
            similarity = self.index.matrix @ self.index.matrix[self.position[canonical.id]]
            similarity = similarity + np.array([0.12 if f.category == canonical.category else 0.0 for f in self.faqs])
            for i in np.argsort(-similarity):
                candidate = self.faqs[int(i)]
                shown = self.display.get(candidate.answer)
                if shown is None or candidate.answer in seen or (candidate.category == CONTACT_CATEGORY != canonical.category):
                    continue
                picks.append(shown)
                seen.add(candidate.answer)
                if len(picks) == count:
                    break
        return picks
