"""Quality gate for the answer / clarify / escalate decision.

Each proposed paraphrase and escalation question is held out of the index in turn, so this measures how the
engine handles wording it has not seen. "WRONG" means a confident answer to a question that should have been
clarified or handed to the team, or a different answer than expected. Re-check the thresholds in config.py
if this fails after the dataset changes.
"""
import json
from pathlib import Path

import pytest

from backend.chatbot.engine import ChatEngine

CASES = json.loads((Path(__file__).parent / "data" / "proposed_cases.json").read_text(encoding="utf-8"))

# Known limits of similarity matching, accepted at approval time (see the Stage 2 report).
KNOWN_GAPS = {
    "What's the worst fall the fund has had?",
    "When was the fund's worst drawdown?",
    "Is the fund's return before or after fees?",
    "What's the NAV?",
    "What are all of the fund's holdings?",
    "When was PineTree Macro founded?",
    # Ambiguous with the definition question when its own row is held out; the real row answers it correctly.
    "What is the management fee?",
}


@pytest.fixture(scope="module")
def engine():
    return ChatEngine()


def outcome(kind, reply, expected_answer=None):
    if kind == "ANSWER":
        if reply.kind == "answer" and reply.text.startswith(expected_answer):
            return "correct"
        return "safe" if reply.kind in ("clarify", "escalate") else "WRONG"
    if kind == "ESCALATE":
        if reply.kind in ("escalate", "contact"):
            return "correct"
        return "safe" if reply.kind == "clarify" else "WRONG"
    if kind == "CLARIFY":
        return "correct" if reply.kind == "clarify" else ("safe" if reply.kind == "escalate" else "WRONG")
    return "correct" if reply.kind == "generic" else "WRONG"


def test_locked_questions_all_answer_correctly(engine):
    locked = [f for f in engine.faqs if f.phase == 1]
    assert len(locked) == 50
    for faq in locked:
        reply = engine.answer(faq.question)
        assert reply.kind == "answer" and reply.text.startswith(faq.answer), faq.id


def test_every_knowledge_question_returns_its_own_answer(engine):
    for case in CASES:
        if case["type"] in ("DIRECT", "PARAPHRASE"):
            reply = engine.answer(case["question"])
            assert reply.kind == "answer" and reply.text.startswith(case["expected_answer"]), case["question"]


def test_generic_conversation_replies(engine):
    for case in CASES:
        if case["type"] == "GENERIC":
            reply = engine.answer(case["question"])
            assert reply.kind == "generic" and reply.text == case["expected_answer"]


def test_approved_follow_up_questions_are_shown_and_answerable(engine):
    expected = {
        "What is the performance fee structure?": ["What is the hurdle rate?", "What is a high watermark?", "What is the management fee?"],
        "What is the minimum initial investment?": ["What is the minimum top-up?", "How often can I invest?", "Is there a redemption fee?"],
        "What is the redemption notice period?": ["Can I withdraw part of my investment?", "Is there a redemption fee?", "How can I contact the team?"],
    }
    for question, follow_ups in expected.items():
        reply = engine.answer(question)
        assert reply.suggestions == follow_ups, question
        for follow_up in follow_ups:
            assert engine.answer(follow_up).kind == "answer", follow_up


def test_follow_ups_are_clean_and_never_repeat_what_was_asked(engine):
    for faq in engine.faqs:
        suggestions = engine.answer(faq.question).suggestions
        assert len(suggestions) == len(set(suggestions))
        for suggestion in suggestions:
            assert suggestion[:1].isupper() and suggestion[-1] in "?.", (faq.question, suggestion)
    asked = {"FAQ_026"}
    assert "What is the hurdle rate?" not in engine.answer("What is the performance fee structure?", asked_ids=asked).suggestions


def test_unseen_wording_never_gets_a_wrong_answer_beyond_known_gaps(engine):
    examples = [c["question"] for c in CASES if c["type"] == "ESCALATE"]
    wrong = []
    for case in CASES:
        t = case["type"]
        if t == "PARAPHRASE":
            reply = engine.answer(case["question"], _exclude_ids={case["faq_id"]})
            result = outcome("ANSWER", reply, case["expected_answer"])
        elif t == "ESCALATE":
            reply = engine.answer(case["question"], _exclude_examples={examples.index(case["question"])})
            result = outcome("ESCALATE", reply)
        elif t == "CLARIFY":
            result = outcome("CLARIFY", engine.answer(case["question"]))
        else:
            continue
        if result == "WRONG":
            wrong.append(case["question"])
    unexpected = set(wrong) - KNOWN_GAPS
    assert not unexpected, f"New wrong answers: {sorted(unexpected)}"
