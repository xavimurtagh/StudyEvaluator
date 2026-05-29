"""Claim <-> study alignment classifier.

For each (claim, study) pair, output one of:
  supports          -- study found a positive effect on the claim's outcome
  partially_supports -- related outcome / effect smaller than claimed / weak
  unrelated         -- study isn't about this claim at all
  contradicts       -- study found null or opposite effect on the claim's outcome

Two-stage approach:
  1. Lexical relevance via TF-IDF cosine between claim and study text. Below
     a threshold -> unrelated, regardless of finding direction.
  2. Direction routing using the per-sentence ExtractedFinding labels we
     already collected: positive -> supports, null -> contradicts (the absence
     of effect contradicts a "X improves Y" claim), negative -> contradicts.

This is deliberately simple. The right upgrade is a fine-tuned NLI model
on SciFact / HealthVer -- the interface (`AlignmentScorer.classify`) is
designed for that swap.
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from api.schemas import (
    AlignmentLabel,
    ClaimEvidenceLink,
    ExtractedFinding,
    ExtractedStudy,
)


RELEVANCE_THRESHOLD = 0.10  # below this, study is treated as unrelated to claim.


@dataclass
class _SentenceMatch:
    text: str
    similarity: float
    direction: str  # 'positive' | 'null' | 'negative'


class AlignmentScorer:
    version = "tfidf-rule-v1"

    def __init__(self):
        self._vectorizer: TfidfVectorizer | None = None
        self._corpus: list[str] = []

    def fit_corpus(self, studies: list[ExtractedStudy]) -> None:
        """Fit IDF on the corpus once so per-claim scoring is consistent."""
        docs = [self._study_doc(s) for s in studies]
        self._vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=5000,
        )
        # Empty corpus -> leave vectorizer unfit; classify() will short-circuit.
        if not any(d.strip() for d in docs):
            self._vectorizer = None
            self._corpus = []
            return
        self._vectorizer.fit(docs)
        self._corpus = docs

    def _study_doc(self, s: ExtractedStudy) -> str:
        parts = [s.title or ""]
        if s.abstract:
            parts.append(s.abstract)
        for f in s.findings:
            parts.append(f.text)
        return " ".join(parts)

    def classify(
        self,
        claim: str,
        study: ExtractedStudy,
    ) -> ClaimEvidenceLink:
        if self._vectorizer is None:
            self.fit_corpus([study])
        if self._vectorizer is None:
            return ClaimEvidenceLink(
                pmid=study.pmid,
                alignment=AlignmentLabel.UNRELATED,
                confidence=1.0,
            )

        # Score relevance at the study level.
        study_doc = self._study_doc(study)
        v = self._vectorizer
        assert v is not None
        sim = float(
            cosine_similarity(
                v.transform([claim]), v.transform([study_doc])
            )[0, 0]
        )
        if sim < RELEVANCE_THRESHOLD:
            return ClaimEvidenceLink(
                pmid=study.pmid,
                alignment=AlignmentLabel.UNRELATED,
                confidence=1.0 - sim,
            )

        # Find the single most claim-relevant finding sentence and use its
        # direction. If no findings were extracted, fall back to title cues.
        matches = self._rank_sentences(claim, study)
        if not matches:
            return ClaimEvidenceLink(
                pmid=study.pmid,
                alignment=AlignmentLabel.PARTIAL,
                confidence=sim,
                quote=None,
            )

        best = matches[0]
        label = self._direction_to_label(best.direction)
        return ClaimEvidenceLink(
            pmid=study.pmid,
            alignment=label,
            confidence=float(min(1.0, 0.5 + best.similarity)),
            quote=best.text,
        )

    def _rank_sentences(
        self, claim: str, study: ExtractedStudy
    ) -> list[_SentenceMatch]:
        sents: list[ExtractedFinding] = list(study.findings)
        if not sents:
            return []
        v = self._vectorizer
        assert v is not None
        claim_vec = v.transform([claim])
        texts = [f.text for f in sents]
        sent_vecs = v.transform(texts)
        sims = cosine_similarity(claim_vec, sent_vecs)[0]
        ranked = sorted(
            (
                _SentenceMatch(text=f.text, similarity=float(sim), direction=f.direction)
                for f, sim in zip(sents, sims)
            ),
            key=lambda m: m.similarity,
            reverse=True,
        )
        # Drop sentences with near-zero overlap; they aren't really evidence.
        return [m for m in ranked if m.similarity >= 0.05]

    @staticmethod
    def _direction_to_label(direction: str) -> AlignmentLabel:
        if direction == "positive":
            return AlignmentLabel.SUPPORTS
        if direction == "negative":
            return AlignmentLabel.CONTRADICTS
        if direction == "inconclusive":
            # Sentence credits something OTHER than the intervention
            # (placebo / another factor). It's not evidence either way.
            return AlignmentLabel.UNRELATED
        # 'null' findings ("no significant difference") contradict
        # "X improves Y" style claims -- absence of effect IS evidence.
        return AlignmentLabel.CONTRADICTS
