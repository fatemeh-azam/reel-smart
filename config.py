"""Reel Smart configuration — all settings in one place."""

from pathlib import Path

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "reel_smart.db"
GAME_EXPORT_DIR = ROOT / "game_export"
GAME_EXPORT_DIR.mkdir(exist_ok=True)

# Seed data (the 92 human-validated phish + 184 legit) lives here.
SEED_PHISH = DATA_DIR / "phish.json"
SEED_LEGIT = DATA_DIR / "legit.json"
TRENDS_FILE = ROOT / "trends" / "trends.json"

# ------------------------------------------------------------------
# Model
# ------------------------------------------------------------------
# The real local model. Override with env var REELSMART_MODEL.
import os
DEFAULT_MODEL = os.environ.get("REELSMART_MODEL", "qwen2.5:14b")

# When Ollama is not reachable, the package falls back to a deterministic
# fake generator/scorer so everything still runs, tests pass, and the
# review desk is browsable. Set REELSMART_FAKE=1 to force fake mode.
FORCE_FAKE = os.environ.get("REELSMART_FAKE", "0") == "1"

MODEL_TEMPERATURES = {
    "conservative": 0.3,
    "creative": 0.9,
    "trend_focused": 0.6,
    "mutator": 0.7,
}

# ------------------------------------------------------------------
# Clue definitions
# ------------------------------------------------------------------
# Base clues are the five the game engine and the seed data use.
BASE_CLUES = ["urgency", "slink", "bgrammer", "tgoodtbt", "pinfo"]

# Extended clues map to specific modern techniques (trend-aware).
EXTENDED_CLUES = [
    "suspiciousQR",
    "callbackRequest",
    "deviceCodeRequest",
    "fakeInvoice",
    "fakeCalendarEvent",
    "urgentDeadline",
    "spoofedSender",
]

# Human-readable labels for the review desk.
CLUE_LABELS = {
    "urgency": "Urgency / pressure",
    "slink": "Suspicious link",
    "bgrammer": "Bad grammar / spelling",
    "tgoodtbt": "Too good to be true",
    "pinfo": "Asks for personal info",
    "suspiciousQR": "QR code (quishing)",
    "callbackRequest": "Call-this-number (vishing)",
    "deviceCodeRequest": "Device / verification code",
    "fakeInvoice": "Fake invoice / payment",
    "fakeCalendarEvent": "Fake calendar invite",
    "urgentDeadline": "Hard deadline",
    "spoofedSender": "Spoofed sender name",
}

# ------------------------------------------------------------------
# Scoring weights (must sum to ~1.0). Tuned so clue-accuracy — the
# thing we can measure objectively — carries real weight.
# ------------------------------------------------------------------
SCORING_WEIGHTS = {
    "clue_accuracy": 0.30,     # do the tagged clues actually exist in the text?
    "complexity_match": 0.20,  # does difficulty match the intended level?
    "effectiveness": 0.20,     # is it realistic (heuristic or LLM)?
    "creativity": 0.15,        # is it novel vs. everything seen so far?
    "trend_relevance": 0.10,   # does it reflect the current trend?
    "safety": 0.05,            # safety gate (fictional brands, no real PII)
}

# ------------------------------------------------------------------
# Evolution parameters
# ------------------------------------------------------------------
POPULATION_SIZE = 10
MAX_GENERATIONS = 6
ELITE_KEEP = 2
CONVERGENCE_SCORE = 8.5   # stop early once best >= this
CONVERGENCE_PATIENCE = 2  # ...and no improvement for this many gens

# ------------------------------------------------------------------
# Audiences
# ------------------------------------------------------------------
# The seed data is kids/family. The adult tier is added for the
# "older adults / general public" audience the project now targets.
AUDIENCES = ["kids_family", "adults"]

# ------------------------------------------------------------------
# Message length — the game shows short cards players scan quickly, so
# generated messages are kept short. target = what the prompt asks for;
# max = a hard trim applied after generation. Tune per audience.
# ------------------------------------------------------------------
LENGTH_LIMITS = {
    "kids_family": {"target_words": 25, "max_words": 40},
    "adults":      {"target_words": 45, "max_words": 70},
}


def length_limit(audience: str) -> dict:
    return LENGTH_LIMITS.get(audience, LENGTH_LIMITS["adults"])
