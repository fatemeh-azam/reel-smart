"""
Multi-dimensional scoring.

Key changes over the original:

* clue_accuracy now uses the detector-vs-claim comparison that actually
  means something (and since generators let the detector author the
  clues, a generated message scores ~1.0 here by construction, while a
  human-edited one is checked honestly).
* effectiveness has a transparent HEURISTIC mode (default) so scores are
  reproducible and calibratable, plus an optional LLM mode. The heuristic
  is what the calibration script tunes against the 92 validated messages.
* a safety scorer penalizes real-PII leakage and rewards fictional-brand
  discipline — this is both a quality signal and a guardrail.

Every score is 0..10. The orchestrator combines them with SCORING_WEIGHTS.
"""

import re
from difflib import SequenceMatcher
from typing import List, Dict, Optional

from config import SCORING_WEIGHTS, DEFAULT_MODEL
from core.models import PhishMessage
from core.clues import ClueDetector, compare_clues
from core import llm


# ---- individual scorers ---------------------------------------------------

class ClueAccuracyScorer:
    """How well do the message's clue flags match what's really in the text?"""
    name = "clue_accuracy"

    def __init__(self):
        self.detector = ClueDetector()

    def score(self, m: PhishMessage) -> float:
        detected, _ = self.detector.detect(m.content, m.link, m.username)
        cmp = compare_clues(m.clues.to_dict(), detected)
        return round(cmp["agreement"] * 10.0, 2)


class ComplexityMatchScorer:
    """
    Does the message's observable 'loudness' match its intended complexity?
    Heuristic and reproducible: counts loud signals (caps, bang, obvious
    bait) and maps the count to a difficulty band.
    """
    name = "complexity_match"

    def score(self, m: PhishMessage) -> float:
        c = m.content
        loud = 0
        loud += len(re.findall(r"\b[A-Z]{4,}\b", c))          # SHOUTING
        loud += c.count("!")                                    # bangs
        loud += len(re.findall(r"\bfree\b|\bwon\b|\bprize\b", c, re.I))
        loud += len(re.findall(r"!!|\$\d", c))
        # observed band: 0-1 subtle, 2-4 moderate, 5+ obvious
        observed = 3 if loud >= 5 else (2 if loud >= 2 else 1)
        dist = abs(observed - m.complexity)
        return round(max(0.0, 10.0 - dist * 4.0), 2)


class EffectivenessScorer:
    """
    How realistic/convincing is it? Heuristic by default (reproducible);
    LLM-backed if use_llm=True and a model is live.
    """
    name = "effectiveness"

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm

    def score(self, m: PhishMessage) -> float:
        if self.use_llm and not llm.is_fake():
            return self._llm_score(m)
        return self._heuristic(m)

    def _heuristic(self, m: PhishMessage) -> float:
        from config import length_limit
        c = m.content
        score = 5.0
        words = len(c.split())
        target = length_limit(m.audience)["target_words"]
        max_w = length_limit(m.audience)["max_words"]
        if 12 <= words <= target + 10:
            score += 1.5                     # on-target length for a game card
        # Penalize messages that run long — the game shows short cards, so a
        # wall of text is a worse training item even if it reads well.
        if words > max_w:
            score -= 2.0
        elif words > target + 15:
            score -= 1.0
        if re.search(r"[.?!]$", c.strip()):
            score += 0.5                      # ends like a sentence
        if not re.search(r"\b[A-Z]{5,}\b", c):
            score += 1.0                      # not shouting
        if c.count("!") <= 1:
            score += 1.0                      # restrained
        if re.search(r"\b(account|verify|confirm|update|security)\b", c, re.I):
            score += 0.5                      # on-theme vocabulary
        if re.search(r"\byour (?:account|order|benefits|package)\b", c, re.I):
            score += 0.5                      # personal relevance hook
        # Subtle messages that read clean get a small bonus.
        if m.complexity == 3 and c.count("!") == 0:
            score += 0.5
        return round(min(10.0, max(0.0, score)), 2)

    def _llm_score(self, m: PhishMessage) -> float:
        prompt = (f"On a 0-10 scale, how convincing would this message be to a "
                  f"typical person (10=very convincing)? Answer with only a number.\n\n{m.content}")
        txt = llm.chat(prompt, 0.1)
        nums = re.findall(r"\d+(?:\.\d+)?", txt)
        if nums:
            return round(min(10.0, max(0.0, float(nums[0]))), 2)
        return 5.0


class CreativityScorer:
    """Novelty vs. everything already seen (seed + prior generations)."""
    name = "creativity"

    def __init__(self, corpus: Optional[List[str]] = None):
        self.corpus = [c.lower() for c in (corpus or [])]

    def score(self, m: PhishMessage) -> float:
        if not self.corpus:
            return 7.0
        text = m.content.lower()
        sim = max(SequenceMatcher(None, text, other).ratio() for other in self.corpus)
        if sim > 0.85:
            return 2.0
        if sim > 0.65:
            return 5.0
        if sim > 0.45:
            return 7.5
        return 9.0


class TrendRelevanceScorer:
    name = "trend_relevance"

    def __init__(self, detector: Optional[ClueDetector] = None):
        self.detector = detector or ClueDetector()
        # Which detected clue signals a technique is actually present.
        self.trend_signals = {
            "QR": "suspiciousQR", "Quishing": "suspiciousQR",
            "Voice": "callbackRequest", "Vishing": "callbackRequest",
            "Callback": "callbackRequest", "Tech Support": "callbackRequest",
            "Device Code": "deviceCodeRequest", "Invoice": "fakeInvoice",
            "Calendar": "fakeCalendarEvent",
        }

    def score(self, m: PhishMessage) -> float:
        if not m.trend:
            return 5.0
        signal = next((v for k, v in self.trend_signals.items() if k in m.trend), None)
        if signal is None:
            return 6.0  # trend with no specific detector signal; neutral-plus
        return 10.0 if getattr(m.clues, signal, 0) == 1 else 3.0


class SafetyScorer:
    """Guardrail: penalize real-PII shapes; reward fictional discipline."""
    name = "safety"

    REAL_PII = [
        r"\b\d{3}-\d{2}-\d{4}\b",                 # SSN
        r"\b(?:\d[ -]*?){13,16}\b",               # card-number-ish
        r"\b[\w.+-]+@(?:gmail|yahoo|outlook|hotmail)\.com\b",  # real inbox
    ]

    def score(self, m: PhishMessage) -> float:
        for pat in self.REAL_PII:
            if re.search(pat, m.content):
                return 0.0
        return 10.0


# ---- orchestrator ---------------------------------------------------------

class ScoringOrchestrator:
    def __init__(self, corpus: Optional[List[str]] = None, use_llm_effectiveness: bool = False):
        self.scorers = [
            ClueAccuracyScorer(),
            ComplexityMatchScorer(),
            EffectivenessScorer(use_llm=use_llm_effectiveness),
            CreativityScorer(corpus=corpus),
            TrendRelevanceScorer(),
            SafetyScorer(),
        ]

    def score_message(self, m: PhishMessage) -> PhishMessage:
        breakdown = {}
        for s in self.scorers:
            try:
                breakdown[s.name] = s.score(m)
            except Exception as e:
                print(f"[score] {s.name} failed: {e}")
                breakdown[s.name] = 5.0
        total = sum(breakdown[n] * w for n, w in SCORING_WEIGHTS.items() if n in breakdown)
        m.score = round(total, 2)
        m.score_breakdown = breakdown
        return m

    def score_population(self, population: List[PhishMessage]) -> List[PhishMessage]:
        scored = [self.score_message(m) for m in population]
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored
