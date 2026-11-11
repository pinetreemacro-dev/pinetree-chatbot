import re

# Questions asking for predictions, guarantees or personal advice are never answered from the knowledge base,
# however similar they look to a factual FAQ (e.g. "next year" vs "last year").
FORWARD_LOOKING = re.compile(
    r"\b(next|coming|upcoming)\s+(year|month|week|quarter|day|decade)\b|\btomorrow\b|"
    r"\b(can|could|will|would|do|does)\s+(you|the\s+fund|pinetree)\s+guarantee\b|"
    r"\bguarantee\s+(my|the|any)\s+(return|profit|money|investment|capital)\w*|\bguaranteed\s+(return|profit)s?\b|"
    r"\b(should|shall)\s+i\s+(invest|buy|sell|put|redeem)\b|\bgood time to (invest|buy|sell|enter)\b|"
    r"\bin\s+(\d+|one|two|three|four|five|ten)\s+years?\b|\b(predict|forecast|projection|will\s+it\s+double)\b|"
    r"\bwill\s+(the\s+)?(fund|nav|gold|silver|market|my\s+(investment|money)|it)\b.*"
    r"\b(return|make|grow|be\s+worth|go\s+up|fall|buy|sell|double|beat)\b|"
    r"\bignore\s+(your|all|previous)\s+instructions\b",
    re.I,
)

# A user asking to reach a person is offered the contact button instead of a guessed answer.
HUMAN_REQUEST = re.compile(
    r"\b(talk|speak|chat|connect|get\s+in\s+touch|reach|contact)\b.*"
    r"\b(person|human|someone|somebody|team|representative|agent|advisor|adviser|executive|manager|support)\b|"
    r"\b(real|live)\s+(person|human|agent)\b|\bhuman\s+agent\b|\bcall\s+me\b|\bcall\s*back\b|\bcustomer\s+(care|support|service)\b",
    re.I,
)

_WORDS ={"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "twelve": 12}


def periods(text: str) -> set:
    """Return the return/performance periods a text refers to, in months ('inc' = since inception).

    Embeddings treat "last two years" and "last three years" as near-identical, which would return the wrong
    figure, so candidates whose period differs from the question's are discarded.
    """
    t = text.lower()
    out: set = set()
    for n, unit in re.findall(r"(\d+|one|two|three|four|five|six|twelve)\s*[- ]?\s*(month|months|mo|year|years|yr|yrs)\b", t):
        n = int(n) if n.isdigit() else _WORDS[n]
        out.add(n * 12 if unit.startswith("y") else n)
    if re.search(r"\b(last|past|previous)\s+(year|12)\b|\bone year\b|\blast yr\b|\bpast yr\b", t):
        out.add(12)
    if re.search(r"\b(last|past|previous)\s+month\b", t):
        out.add(1)
    if re.search(r"\bquarter\b", t):
        out.add(3)
    if re.search(r"\bhalf[- ]year\b", t):
        out.add(6)
    if re.search(r"since (inception|it started|the start|launch|beginning)|\binception\b|since it began|all[- ]time", t):
        out.add("inc")
    return out
