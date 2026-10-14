"""Export approved rounds to the game's JSON format."""

import json
from datetime import datetime

from config import GAME_EXPORT_DIR
from core.database import Database


def export_game_json(db: Database) -> str:
    """Write approved rounds to game_export/rounds.json. Returns the path."""
    rounds = db.approved_rounds()
    payload = {
        "exported_at": datetime.now().isoformat(),
        "round_count": len(rounds),
        "rounds": [],
    }
    for r in rounds:
        if not r["phish"]:
            continue
        p = r["phish"]
        payload["rounds"].append({
            "id": p["id"],
            "theme": r["theme"],
            "complexity": r["complexity"],
            "trend": r["trend"],
            "audience": r["audience"],
            "phish": {
                "username": p["username"],
                "content": p["content"],
                "link": p["link"],
                # Game engine consumes the 5 base clues only.
                "clues": {k: p["clues"][k] for k in
                          ["urgency", "slink", "bgrammer", "tgoodtbt", "pinfo"]},
            },
            "legit": [
                {"username": l["username"], "content": l["content"], "link": l.get("link", "")}
                for l in r["legit"]
            ],
        })
    out = GAME_EXPORT_DIR / "rounds.json"
    out.write_text(json.dumps(payload, indent=2))
    return str(out)
