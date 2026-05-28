"""Parse a free-text health claim into (subject, predicate).

Example:
    "Collagen supplements regrow hair"
        -> subject="collagen supplements", predicate="regrows hair"
    "Ashwagandha reduces stress and anxiety"
        -> subject="ashwagandha", predicate="reduces stress and anxiety"
    "Magnesium helps with sleep"
        -> subject="magnesium", predicate="improves sleep"

Heuristic, not an LLM call -- this is the kind of thing a fine-tuned NER
model would do better, but the regex form is good enough for the demo and
keeps the API key-free. Designed so a swap-in is one function.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Verbs we recognize as introducing a claim. Map to a normalized predicate
# form so "boosts X" and "increases X" don't show up as separate claims.
VERB_NORMALIZE: list[tuple[str, str]] = [
    (r"\b(regrow|regrows|regrowing|regrew)\b", "regrows"),
    (r"\b(boost|boosts|boosting|boosted|increase|increases|increasing|increased)\b", "improves"),
    (r"\b(enhance|enhances|enhancing|enhanced|improve|improves|improving|improved)\b", "improves"),
    (r"\b(reduce|reduces|reducing|reduced|lower|lowers|lowering|lowered|decrease|decreases|decreasing|decreased)\b", "reduces"),
    (r"\b(prevent|prevents|preventing|prevented)\b", "prevents"),
    (r"\b(cure|cures|curing|cured)\b", "cures"),
    (r"\b(treat|treats|treating|treated)\b", "treats"),
    (r"\b(help|helps|helping|helped)\s+with\b", "improves"),
    (r"\b(help|helps|helping|helped)\b", "improves"),
    (r"\b(support|supports|supporting|supported)\b", "improves"),
    (r"\b(promote|promotes|promoting|promoted)\b", "improves"),
    (r"\b(cause|causes|causing|caused)\b", "causes"),
    (r"\b(is good for|are good for)\b", "improves"),
]

# Tokens to strip from the subject -- marketing fluff that adds no info.
SUBJECT_STOPS = {
    "the",
    "a",
    "an",
    "this",
    "these",
    "those",
    "that",
    "my",
    "your",
    "their",
    "his",
    "her",
    "our",
    "some",
    "any",
    "new",
    "amazing",
    "best",
    "natural",
    "organic",
    "premium",
}


@dataclass
class ParsedClaim:
    subject: str
    predicate: str
    raw: str


def parse_claim(text: str) -> ParsedClaim | None:
    """Return the parsed claim, or None if no verb structure is found."""
    raw = text.strip().rstrip(".!?")
    if not raw:
        return None

    lowered = raw.lower()
    for pattern, normalized in VERB_NORMALIZE:
        m = re.search(pattern, lowered)
        if not m:
            continue
        subject = lowered[: m.start()].strip(" ,;:")
        rest = lowered[m.end() :].strip(" ,;:")
        if not subject or not rest:
            continue
        subject = _clean_subject(subject)
        if not subject:
            continue
        predicate = f"{normalized} {rest}"
        return ParsedClaim(subject=subject, predicate=predicate, raw=raw)

    # No verb structure -- fall back to treating the entire input as a
    # product query with no specific predicate.
    return ParsedClaim(subject=_clean_subject(lowered), predicate="", raw=raw)


def _clean_subject(s: str) -> str:
    tokens = [
        t for t in re.split(r"\s+", s) if t and t.lower() not in SUBJECT_STOPS
    ]
    # Trailing "supplement(s)", "pills", "capsules" etc. are fine -- keep
    # them so the search hits the right corpus.
    return " ".join(tokens).strip()
