"""Discover candidate marketed claims from the corpus.

Two paths:
  - User provides claims explicitly (preferred for fact-checking flows).
  - Pipeline derives them from study titles + findings.

Derivation strategy: pull verb-phrase patterns like "improves X", "reduces Y",
"increases Z" from study findings, cluster by the object noun, and keep the
most-mentioned ones. Cheap, predictable, and a labeled dataset of
"social-media-style claims" would later let us train a generation model on
the same input.
"""

from __future__ import annotations

import re
from collections import Counter

from api.schemas import ExtractedStudy

CLAIM_PATTERNS = [
    # "improves X", "improved Y", "reduces Z", etc.
    re.compile(
        r"\b(improv\w*|increas\w*|reduc\w*|decreas\w*|enhanc\w*|prevent\w*|lower\w*|boost\w*)"
        r"\s+(?:in\s+|the\s+)?([a-z][a-z\-]{3,40}(?:\s+[a-z][a-z\-]{3,40})?)",
        re.IGNORECASE,
    ),
]

STOP_OBJECTS = {
    "study",
    "studies",
    "trial",
    "trials",
    "group",
    "groups",
    "patients",
    "participants",
    "subjects",
    "data",
    "outcomes",
    "results",
    "effects",
    "effect",
    "levels",
    "values",
    "scores",
    "score",
    "compared",
    "control",
    "treatment",
    "intervention",
    "placebo",
}


def _normalize_object(obj: str) -> str:
    obj = re.sub(r"\s+", " ", obj.strip().lower())
    obj = re.sub(r"[^a-z\s-]", "", obj)
    return obj


def _verb_to_action(verb: str) -> str:
    v = verb.lower()
    if v.startswith(("improv", "enhanc", "boost", "increas")):
        return "improves"
    if v.startswith(("reduc", "decreas", "lower", "prevent")):
        return "reduces"
    return "affects"


def derive_claims(studies: list[ExtractedStudy], top_k: int = 5) -> list[str]:
    """Return up to `top_k` candidate claims of the form 'X improves Y'."""
    counter: Counter[tuple[str, str]] = Counter()
    for s in studies:
        blobs = [f.text for f in s.findings if f.direction != "null"] + [s.title]
        for blob in blobs:
            for pat in CLAIM_PATTERNS:
                for m in pat.finditer(blob):
                    action = _verb_to_action(m.group(1))
                    obj = _normalize_object(m.group(2))
                    head = obj.split()[0] if obj else ""
                    if not obj or head in STOP_OBJECTS or len(obj) < 4:
                        continue
                    counter[(action, obj)] += 1

    claims: list[str] = []
    seen_objects: set[str] = set()
    for (action, obj), _count in counter.most_common(top_k * 4):
        # Keep one claim per object so the list isn't dominated by one outcome.
        if obj in seen_objects:
            continue
        seen_objects.add(obj)
        claims.append(f"{action} {obj}")
        if len(claims) >= top_k:
            break
    return claims
