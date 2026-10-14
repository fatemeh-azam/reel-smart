#!/usr/bin/env python3
"""
Calibrate the detector and scorer against the 92 human-validated seed
messages.

This is the credibility step. It measures, per base clue, how often the
detector's output matches the human label, and prints a confusion summary.
A detector you can't trust makes every downstream score meaningless, so
this number is the one to quote.

Run:  python3 scripts/calibrate.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import BASE_CLUES, CLUE_LABELS
from core.seed import load_seed
from core.clues import ClueDetector


def main():
    phish, _ = load_seed()
    det = ClueDetector()

    # Per-clue confusion counts.
    stats = {c: {"tp": 0, "tn": 0, "fp": 0, "fn": 0} for c in BASE_CLUES}
    total_agree = 0
    total_cells = 0

    for m in phish:
        detected, _ = det.detect(m.content, m.link, m.username)
        human = m.clues.base_dict()
        auto = detected.base_dict()
        for c in BASE_CLUES:
            h, a = human[c], auto[c]
            total_cells += 1
            if h == a:
                total_agree += 1
            if h == 1 and a == 1:
                stats[c]["tp"] += 1
            elif h == 0 and a == 0:
                stats[c]["tn"] += 1
            elif h == 0 and a == 1:
                stats[c]["fp"] += 1
            else:
                stats[c]["fn"] += 1

    print("=" * 64)
    print(f"CALIBRATION against {len(phish)} human-validated messages")
    print("=" * 64)
    print(f"\nOverall agreement: {total_agree}/{total_cells} "
          f"= {100*total_agree/total_cells:.1f}%\n")
    print(f"{'clue':<22}{'prec':>7}{'recall':>8}{'F1':>7}   (tp/fp/fn)")
    print("-" * 60)
    macro_f1 = []
    for c in BASE_CLUES:
        s = stats[c]
        prec = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) else 0.0
        rec = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        macro_f1.append(f1)
        print(f"{CLUE_LABELS[c]:<22}{prec:>7.2f}{rec:>8.2f}{f1:>7.2f}   "
              f"({s['tp']}/{s['fp']}/{s['fn']})")
    print("-" * 60)
    print(f"{'macro F1':<22}{'':>7}{'':>8}{sum(macro_f1)/len(macro_f1):>7.2f}")
    print("\nInterpretation: high precision means when the detector flags a "
          "clue it is usually right;\nhigh recall means it rarely misses a "
          "human-tagged clue. Tune patterns in core/clues.py\nand re-run to "
          "move these numbers.")


if __name__ == "__main__":
    main()
