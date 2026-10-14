"""
LLM client wrapper.

Tries real Ollama first. If Ollama is not installed or not reachable
(or REELSMART_FAKE=1), it transparently falls back to a deterministic
"fake" backend so the whole package runs, tests pass, and the review
desk is browsable without a model. The fake backend is seeded, so runs
are reproducible.

Nothing else in the codebase needs to know which backend is live —
call `chat(prompt, temperature)` and check `BACKEND` if you want to
display it.
"""

import os
import random
import hashlib

from config import DEFAULT_MODEL, FORCE_FAKE

BACKEND = "unknown"
_client_ready = False
_ollama = None


def _try_ollama() -> bool:
    global _ollama, BACKEND, _client_ready
    if FORCE_FAKE:
        BACKEND = "fake (forced)"
        return False
    try:
        import ollama  # type: ignore
        # Probe: list models. If the daemon is down this raises.
        ollama.list()
        _ollama = ollama
        BACKEND = f"ollama:{DEFAULT_MODEL}"
        _client_ready = True
        return True
    except Exception as e:
        BACKEND = "fake (ollama unavailable)"
        return False


_try_ollama()


# ---------------------------------------------------------------------------
# Fake backend — deterministic, offline, good enough to exercise the pipeline
# ---------------------------------------------------------------------------

_FAKE_BRANDS = {
    "Microsoft": "Microsoft Account Team",
    "School": "School IT Department",
    "Bank": "Account Services",
    "Medicare": "Benefits Coordination Center",
    "IRS": "Tax Processing Unit",
    "USPS": "Delivery Notifications",
    "Amazon": "Order Support",
}

_FAKE_TEMPLATES = {
    "QR Code Phishing (Quishing)": (
        "Your {theme} account needs re-verification. Scan the QR code below "
        "within 24 hours to confirm your details, or your access may be limited."
    ),
    "Voice Phishing (Vishing) Callback": (
        "We detected unusual activity on your {theme} account. Please call our "
        "support line at 1-888-555-0147 immediately to confirm your identity."
    ),
    "Invoice Fraud": (
        "Invoice #INV-4471 from {theme} is now past due. Please review the "
        "outstanding balance and submit payment to avoid late fees."
    ),
    "Tech Support Scam": (
        "{theme} Security has detected a virus on your device. Call our "
        "certified technicians now and provide the code shown on your screen."
    ),
    "Grandparent / Emergency Scam": (
        "Hi, it's your grandson. I'm in trouble and need help fast. Please don't "
        "tell anyone — just send a gift card code to this number right away."
    ),
    "Medicare / Benefits Scam": (
        "Your {theme} benefits require immediate verification. Confirm your ID "
        "number and date of birth within 48 hours to keep your coverage active."
    ),
    "_default": (
        "Important notice from {theme}: we need you to verify your account "
        "information. Please confirm your details as soon as possible."
    ),
}


def _seed_from(prompt: str) -> int:
    return int(hashlib.sha256(prompt.encode()).hexdigest(), 16) % (2**32)


def _fake_message(theme: str, trend: str, complexity: int, rng: random.Random) -> str:
    base = _FAKE_TEMPLATES.get(trend, _FAKE_TEMPLATES["_default"]).format(theme=theme)
    if complexity == 1:
        # obvious: shout + extra bait
        base = "URGENT!! " + base + " Claim your FREE reward now!!"
    elif complexity == 3:
        # subtle: strip the loud signals
        base = base.replace("immediately", "at your earliest convenience")
        base = base.replace("within 24 hours", "soon")
    return base


def fake_chat(prompt: str, temperature: float = 0.5) -> str:
    """Deterministic stand-in for an LLM completion."""
    rng = random.Random(_seed_from(prompt + f"{temperature:.2f}"))
    # The generators call with structured prompts; we sniff theme/trend/
    # complexity out of the prompt text so output is relevant.
    theme = "your provider"
    for t in _FAKE_BRANDS:
        if t.lower() in prompt.lower():
            theme = t
            break
    trend = "_default"
    for t in _FAKE_TEMPLATES:
        if t != "_default" and t.lower() in prompt.lower():
            trend = t
            break
    complexity = 2
    for c in ("1", "2", "3"):
        if f"complexity: {c}" in prompt.lower() or f"complexity {c}" in prompt.lower():
            complexity = int(c)
            break
    return _fake_message(theme, trend, complexity, rng)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chat(prompt: str, temperature: float = 0.5) -> str:
    """Return a completion string. Never raises for backend reasons."""
    if _client_ready and _ollama is not None:
        try:
            resp = _ollama.chat(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": temperature},
            )
            return resp["message"]["content"]
        except Exception as e:
            # Fall through to fake on any runtime failure.
            print(f"[llm] ollama call failed ({e}); using fake backend")
    return fake_chat(prompt, temperature)


def is_fake() -> bool:
    return not _client_ready
