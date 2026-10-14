"""
Load the human-validated seed data (92 phish + 184 legit) and pair it
correctly.

The original legit.json keys two legitimate messages under the SAME id as
their phish partner, so loading into a dict keyed by id silently dropped
half the data. Here we group legit by id into a list, so every phish keeps
both of its legit partners.

The seed phish are treated as GROUND TRUTH for calibration: their human
clue tags are what we measure the detector and scorer against.
"""

import json
from typing import List, Dict, Tuple
from collections import defaultdict

from config import SEED_PHISH, SEED_LEGIT
from core.models import PhishMessage, LegitMessage, Clues


def load_seed() -> Tuple[List[PhishMessage], Dict[int, List[LegitMessage]]]:
    phish_raw = json.loads(SEED_PHISH.read_text())
    legit_raw = json.loads(SEED_LEGIT.read_text())

    phish: List[PhishMessage] = []
    for p in phish_raw:
        phish.append(PhishMessage(
            id=p["id"],
            username=p.get("username", ""),
            avatar=p.get("avatar", ""),
            content=p.get("content", "").strip(),
            link=p.get("link", ""),
            clues=Clues.from_dict(p.get("clues", {})),
            complexity=p.get("complexity", 2),
            audience="kids_family",
            source="seed",
            status="approved",   # human-validated already
        ))

    legit_by_id: Dict[int, List[LegitMessage]] = defaultdict(list)
    for l in legit_raw:
        legit_by_id[l["id"]].append(LegitMessage(
            id=l["id"],
            username=l.get("username", ""),
            avatar=l.get("avatar", ""),
            content=l.get("content", "").strip(),
            link=l.get("link", ""),
            audience="kids_family",
        ))

    return phish, dict(legit_by_id)


def seed_corpus() -> List[str]:
    """All seed message texts, for the creativity scorer."""
    phish, legit_by_id = load_seed()
    texts = [p.content for p in phish]
    for group in legit_by_id.values():
        texts.extend(m.content for m in group)
    return texts
