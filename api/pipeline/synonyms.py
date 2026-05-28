"""Lay-term -> biomedical-term expansion for PubMed queries.

People search using everyday names ("sun cream", "fish oil"). PubMed indexes
biomedical names ("sunscreen", "omega-3 fatty acids"). Without expansion, the
search returns a thin corpus and the verdict ends up under-evidenced.

Two layers:
  1. Curated lay -> biomedical dictionary (this module). Fast, deterministic,
     covers the high-traffic cases.
  2. PubMed's own term-translation as a fallback inspected at search time
     (see ``ingest.py``). Out of scope for this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Curated mapping. Keys are lowercased lay terms; values are the canonical
# biomedical term PubMed indexes well. Add entries as they come up rather
# than trying to be exhaustive up front.
LAY_TO_BIOMEDICAL: dict[str, str] = {
    "sun cream": "sunscreen",
    "suncream": "sunscreen",
    "sun screen": "sunscreen",
    "spf": "sunscreen",
    "fish oil": "omega-3 fatty acids",
    "fish oils": "omega-3 fatty acids",
    "omega 3": "omega-3 fatty acids",
    "omega-3": "omega-3 fatty acids",
    "cbd": "cannabidiol",
    "cbd oil": "cannabidiol",
    "thc": "tetrahydrocannabinol",
    "vitamin c": "ascorbic acid",
    "vitamin b3": "niacin",
    "vitamin b9": "folic acid",
    "vitamin b12": "cobalamin",
    "tylenol": "acetaminophen",
    "paracetamol": "acetaminophen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "aleve": "naproxen",
    "aspirin": "acetylsalicylic acid",
    "baby aspirin": "acetylsalicylic acid",
    "diet coke": "aspartame",
    "splenda": "sucralose",
    "stevia": "steviol glycosides",
    "monk fruit": "mogroside",
    "salt": "sodium chloride",
    "table salt": "sodium chloride",
    "sea salt": "sodium chloride",
    "baking soda": "sodium bicarbonate",
    "apple cider vinegar": "acetic acid",
    "matcha": "green tea",
    "weed": "cannabis",
    "marijuana": "cannabis",
    "shrooms": "psilocybin",
    "magic mushrooms": "psilocybin",
    "vape": "electronic cigarette",
    "e-cig": "electronic cigarette",
    "e cigarette": "electronic cigarette",
    "ozempic": "semaglutide",
    "wegovy": "semaglutide",
    "mounjaro": "tirzepatide",
    "zepbound": "tirzepatide",
    "viagra": "sildenafil",
    "cialis": "tadalafil",
    "prozac": "fluoxetine",
    "zoloft": "sertraline",
    "lexapro": "escitalopram",
    "adderall": "amphetamine",
    "ritalin": "methylphenidate",
    "xanax": "alprazolam",
    "ambien": "zolpidem",
    "melatonin gummies": "melatonin",
    "collagen powder": "collagen",
    "collagen peptides": "collagen",
    "whey protein": "whey proteins",
    "creatine": "creatine monohydrate",
    "pre workout": "caffeine",
    "pre-workout": "caffeine",
    "energy drink": "caffeine",
    "red bull": "caffeine",
    "monster energy": "caffeine",
    "kombucha": "fermented tea",
    "bone broth": "collagen",
    "celery juice": "apium graveolens",
    "ashwagandha": "withania somnifera",
    "turmeric": "curcumin",
    "ginger": "zingiber officinale",
    "garlic": "allium sativum",
    "ginkgo": "ginkgo biloba",
    "st johns wort": "hypericum perforatum",
    "st john's wort": "hypericum perforatum",
    "valerian": "valeriana officinalis",
    "elderberry": "sambucus",
    "echinacea": "echinacea purpurea",
}


@dataclass
class ExpandedQuery:
    """Result of expanding a user query for PubMed search."""

    original: str
    canonical: str  # what we'll actually search for
    pubmed_query: str  # full PubMed search expression
    expansions: list[str] = field(default_factory=list)  # human-readable notes

    @property
    def was_expanded(self) -> bool:
        return self.canonical.lower().strip() != self.original.lower().strip()


def expand_query(text: str) -> ExpandedQuery:
    """Expand a lay-term query into a biomedical PubMed search.

    Tries the curated dictionary first. Falls through to the original term
    unchanged if no entry matches.
    """
    original = text.strip()
    key = original.lower()
    expansions: list[str] = []

    canonical = LAY_TO_BIOMEDICAL.get(key)
    if canonical is None:
        # Try without trailing punctuation / common qualifiers.
        stripped = key.rstrip(".?!,")
        canonical = LAY_TO_BIOMEDICAL.get(stripped)

    if canonical is None:
        canonical = original
    else:
        expansions.append(f"'{original}' expanded to '{canonical}'")

    return ExpandedQuery(
        original=original,
        canonical=canonical,
        pubmed_query=_to_pubmed(canonical),
        expansions=expansions,
    )


def _to_pubmed(term: str) -> str:
    t = term.strip()
    if " " in t or "-" in t:
        return f'"{t}"[Title/Abstract] OR "{t}"[MeSH Terms]'
    return f"{t}[Title/Abstract] OR {t}[MeSH Terms]"
