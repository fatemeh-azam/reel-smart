"""Load and sample phishing trends, weighted by how current they are."""

import json
import random
from typing import List, Dict, Optional

from config import TRENDS_FILE


def load_trends(audience: Optional[str] = None) -> List[Dict]:
    data = json.loads(TRENDS_FILE.read_text())
    trends = data["trends"]
    if audience:
        trends = [t for t in trends if audience in t.get("audience", [])]
    return trends


def sample_trend(audience: Optional[str] = None,
                 rng: Optional[random.Random] = None) -> Dict:
    rng = rng or random
    trends = load_trends(audience)
    weights = [t.get("weight", 0.5) for t in trends]
    return rng.choices(trends, weights=weights, k=1)[0]


def trend_by_name(name: str) -> Optional[Dict]:
    for t in load_trends():
        if t["name"] == name:
            return t
    return None
