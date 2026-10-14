"""
Defenses for the Reel Smart pipeline.

These are the controls the red-team script turns ON to show before/after.
Each is small, readable, and maps to a named attack:

  * sanitize_trend_feed   -> poisoned trend feed (prompt injection via data)
  * guard_scorer_output   -> scorer manipulation (message tells scorer "rate 10")
  * scan_for_secrets      -> data leakage (planted secrets reaching logs/output)
  * enforce_fiction       -> misuse (output must use fictional brands/PII)
"""

import re
from typing import Dict, List, Tuple

# ---- 1. Trend-feed sanitization (poisoned data / indirect injection) ----

_INJECTION_PATTERNS = [
    # instruction-override phrasings
    r"ignore (?:all |the )?(?:previous|above) instructions",
    r"disregard (?:all |the )?(?:previous|prior)",
    r"system prompt", r"you are now", r"you are no longer",
    r"new instructions?:", r"no longer (?:limited|restricted|bound)",
    # attempts to defeat the safety / fiction rule
    r"real-?looking (?:account|card|ssn|personal)",
    r"(?:use|include|add) (?:a )?real (?:account|name|person|address|ssn)",
    r"append (?:the )?(?:url|link|text)", r"to every message",
    # scorer-manipulation phrasings
    r"rate this (?:a |as )?10", r"give (?:it |this )?(?:a )?(?:perfect|max|10)",
    # prompt-exfiltration phrasings
    r"output your", r"reveal (?:your|the) (?:prompt|instructions|system)",
    r"print (?:your|the) (?:prompt|instructions)",
]


def sanitize_trend_feed(trend: Dict) -> Tuple[Dict, List[str]]:
    """Strip injection attempts from untrusted trend text. Returns (clean, flags)."""
    flags = []
    clean = dict(trend)
    for field in ("name", "description"):
        val = str(trend.get(field, ""))
        for pat in _INJECTION_PATTERNS:
            if re.search(pat, val, re.I):
                flags.append(f"{field}: matched /{pat}/")
                val = re.sub(pat, "[removed]", val, flags=re.I)
        clean[field] = val
    return clean, flags


# ---- 2. Scorer-output guarding (scorer manipulation) ----

def guard_scorer_output(raw_score, lo: float = 0.0, hi: float = 10.0) -> float:
    """
    Never trust free-form scorer output. Coerce to a number and clamp.
    A message that tries to talk the scorer into a 10 still can't exceed
    the clamp, and non-numeric output fails closed to the midpoint.
    """
    try:
        v = float(raw_score)
    except (TypeError, ValueError):
        return (lo + hi) / 2
    return max(lo, min(hi, v))


def message_attempts_scorer_injection(content: str) -> List[str]:
    """Detect a message trying to instruct the scorer."""
    hits = []
    for pat in _INJECTION_PATTERNS:
        if re.search(pat, content, re.I):
            hits.append(pat)
    return hits


# ---- 3. Secret scanning (data leakage) ----

_SECRET_PATTERNS = {
    "api_key": r"\b(?:sk|pk|api|key)[-_](?:live|test|prod)?[-_]?[A-Za-z0-9]{12,}\b",
    "aws_key": r"\bAKIA[0-9A-Z]{16}\b",
    "bearer": r"\bBearer\s+[A-Za-z0-9._-]{20,}\b",
    "private_key": r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
    "password_assign": r"(?:password|passwd|pwd)\s*[:=]\s*\S+",
}


def scan_for_secrets(text: str) -> Dict[str, List[str]]:
    found = {}
    for name, pat in _SECRET_PATTERNS.items():
        m = re.findall(pat, text)
        if m:
            found[name] = m
    return found


def redact_secrets(text: str) -> str:
    out = text
    for pat in _SECRET_PATTERNS.values():
        out = re.sub(pat, "[REDACTED]", out)
    return out


# ---- 4. Fiction enforcement (misuse resistance) ----

_REAL_PII = [
    r"\b\d{3}-\d{2}-\d{4}\b",                    # SSN
    r"\b(?:\d[ -]*?){13,16}\b",                  # card number
    r"\b[\w.+-]+@(?:gmail|yahoo|outlook|hotmail)\.com\b",
]


def enforce_fiction(content: str) -> Tuple[bool, List[str]]:
    """Reject output that embeds real-looking PII. Returns (ok, reasons)."""
    reasons = []
    for pat in _REAL_PII:
        if re.search(pat, content):
            reasons.append(f"real-PII pattern /{pat}/")
    return (not reasons), reasons
