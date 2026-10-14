#!/usr/bin/env python3
"""
Run the evolution loop and save candidates to the database for review.

Usage (interactive):   python3 scripts/run_evolution.py
Usage (flags):         python3 scripts/run_evolution.py --audience adults \
                           --trend "Tech Support Scam" --theme Bank --complexity 1

Generated messages land in the database with status 'candidate'. Open the
review desk (streamlit run review/app.py) to approve/edit/reject them.
"""

import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import AUDIENCES
from core import llm
from core.database import Database
from core.seed import seed_corpus
from core.evolution import run_evolution
from trends.trend_tracker import load_trends, trend_by_name


def pick(prompt, options):
    print(f"\n{prompt}")
    for i, o in enumerate(options):
        print(f"  {i+1}. {o}")
    raw = input("Select (number): ").strip()
    try:
        return options[int(raw) - 1]
    except Exception:
        print(f"  -> defaulting to {options[0]}")
        return options[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audience", choices=AUDIENCES)
    ap.add_argument("--trend")
    ap.add_argument("--theme")
    ap.add_argument("--complexity", type=int, choices=[1, 2, 3])
    ap.add_argument("--llm-effectiveness", action="store_true",
                    help="use the LLM (not the heuristic) for the effectiveness score")
    args = ap.parse_args()

    print("=" * 60)
    print("  REEL SMART — evolution")
    print(f"  LLM backend: {llm.BACKEND}")
    print("=" * 60)

    audience = args.audience or pick("Audience:", AUDIENCES)
    trends = load_trends(audience)
    trend = (trend_by_name(args.trend) if args.trend
             else pick("Trend:", [t["name"] for t in trends]))
    if isinstance(trend, str):
        trend = next(t for t in trends if t["name"] == trend)
    theme = args.theme or pick("Theme:", ["Microsoft", "School", "Bank", "Amazon", "USPS", "Medicare"])
    complexity = args.complexity or trend.get("default_complexity", 2)

    db = Database()
    start_id = db.next_phish_id()
    corpus = seed_corpus()

    def on_gen(rec, pop):
        print(f"  gen {rec.generation}: best={rec.best_score:.2f} avg={rec.avg_score:.2f}")
        db.save_evolution(rec)

    print(f"\nRunning: {trend['name']} / {theme} / complexity {complexity} / {audience}")
    best, all_scored, records = run_evolution(
        trend=trend, theme=theme, complexity=complexity, audience=audience,
        seed_corpus=corpus, start_id=start_id, on_generation=on_gen,
        use_llm_effectiveness=args.llm_effectiveness,
    )

    db.save_phish_batch(all_scored)
    print(f"\nSaved {len(all_scored)} candidates to the database.")
    if best:
        print(f"\nBest (score {best.score:.2f}):\n  {best.content}")
        print(f"  clues: {best.clues.active()}")
    print("\nNext: streamlit run review/app.py  — to review and approve.")


if __name__ == "__main__":
    main()
