"""
Reel Smart Review Desk (Streamlit).

The human-in-the-loop. Every generated candidate is shown with:
  * its score and the full breakdown,
  * the clues the detector found, highlighted IN the message text,
  * approve / edit / reject controls.

Approved candidates are paired with two legitimate decoys and exported to
the game's JSON. Generation stays OFFLINE (on your Mac); only approved,
reviewed content ever leaves this desk. That review gate is the project's
core safety control.

Run:  streamlit run review/app.py
"""

import sys
import html
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from config import CLUE_LABELS, SCORING_WEIGHTS
from core import llm
from core.database import Database
from core.clues import ClueDetector, compare_clues
from core.seed import load_seed
from core.export import export_game_json
from core.models import LegitMessage

st.set_page_config(page_title="Reel Smart Review Desk", layout="wide")

db = Database()
detector = ClueDetector()


@st.cache_data
def _legit_pool():
    _, legit_by_id = load_seed()
    pool = []
    for group in legit_by_id.values():
        pool.extend(group)
    return pool


def highlight(content: str, spans: dict) -> str:
    """Wrap matched clue snippets in colored marks."""
    colors = {
        "urgency": "#fde68a", "slink": "#fecaca", "bgrammer": "#ddd6fe",
        "tgoodtbt": "#bbf7d0", "pinfo": "#bfdbfe", "suspiciousQR": "#fbcfe8",
        "callbackRequest": "#c7d2fe", "deviceCodeRequest": "#a5f3fc",
        "fakeInvoice": "#fed7aa", "fakeCalendarEvent": "#e9d5ff",
        "urgentDeadline": "#fef08a", "spoofedSender": "#fca5a5",
    }
    out = html.escape(content)
    # Longest snippets first so nested matches don't break.
    snippets = []
    for clue, matches in spans.items():
        for s in matches:
            snippets.append((s, clue))
    snippets.sort(key=lambda x: len(x[0]), reverse=True)
    for snippet, clue in snippets:
        color = colors.get(clue, "#e5e7eb")
        esc = html.escape(snippet)
        pat = re.escape(esc)
        out = re.sub(
            pat,
            f'<mark style="background:{color};padding:0 2px;border-radius:3px" '
            f'title="{CLUE_LABELS.get(clue, clue)}">{esc}</mark>',
            out, count=1,
        )
    return out


# ---- sidebar ----
st.sidebar.title("Reel Smart")
st.sidebar.caption(f"LLM backend: {llm.BACKEND}")
if llm.is_fake():
    st.sidebar.info("Running with the offline fake backend. Start Ollama "
                    "and rerun generation for real model output.")

candidates = db.candidates("candidate")
approved = db.candidates("approved")
st.sidebar.metric("Awaiting review", len(candidates))
st.sidebar.metric("Approved", len([a for a in approved if a.source != 'seed']))

if st.sidebar.button("Export approved → game JSON"):
    path = export_game_json(db)
    st.sidebar.success(f"Exported to {path}")

st.sidebar.divider()
st.sidebar.caption("Safety model: generation is offline; only reviewed, "
                   "approved rounds are exported. No live scam generator is "
                   "ever exposed.")

# ---- main ----
st.title("Review Desk")
st.write("Each candidate below was written offline and scored automatically. "
         "The highlights show what the **clue detector** found — approve, edit, "
         "or reject.")

if not candidates:
    st.success("No candidates awaiting review. Run "
               "`python3 scripts/run_evolution.py` to generate some.")
    st.stop()

pool = _legit_pool()

for m in candidates:
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**{m.username}**  ·  _{m.trend} / {m.theme} / "
                        f"complexity {m.complexity} / {m.audience}_")
            st.markdown(
                f'<div style="font-size:1.05rem;line-height:1.6">'
                f'{highlight(m.content, m.clue_spans)}</div>',
                unsafe_allow_html=True)
            if m.link:
                st.caption(f"link: {m.link}")
            active = m.clues.active()
            if active:
                st.caption("Clues detected: " +
                           ", ".join(CLUE_LABELS.get(a, a) for a in active))
        with c2:
            st.metric("Score", f"{m.score:.2f}")
            with st.expander("breakdown"):
                for k, w in SCORING_WEIGHTS.items():
                    v = m.score_breakdown.get(k, 0)
                    st.write(f"{k}: {v:.1f} × {w}")

        # actions
        a1, a2, a3 = st.columns(3)
        if a1.button("✓ Approve", key=f"ap{m.id}"):
            # pick two legit decoys at random from the pool
            import random
            decoys = random.sample(pool, 2)
            db.approve_round(m, decoys[0], decoys[1])
            st.rerun()
        if a3.button("✗ Reject", key=f"rj{m.id}"):
            db.set_status(m.id, "rejected")
            st.rerun()
        with st.expander("Edit"):
            new_text = st.text_area("Message text", m.content, key=f"ed{m.id}")
            if st.button("Save edit (re-detect clues)", key=f"sv{m.id}"):
                m.content = new_text
                clues, spans = detector.detect(new_text, m.link, m.username)
                m.clues = clues
                m.clue_spans = spans
                db.update_content(m)
                st.success("Saved and re-detected clues.")
                st.rerun()
