# Reel Smart

An AI system that generates phishing-awareness training content for an educational
game, and a security review of that AI system itself.

Reel Smart runs a generate, score, and evolve loop with a local LLM to produce
realistic but fictional phishing messages, tags each with the red-flag "clues" a
learner should spot, and routes every candidate through a human review step before
anything is exported to the game. Generation runs entirely offline; only reviewed,
approved content leaves the review desk.

It covers two audiences from one engine: a kids and family set, and an adults tier
(tech-support, Medicare, grandparent-emergency, invoice, and voice-phishing scams).

---

## Why it is built this way

**The detector, not the model, authors the clue tags.** Every generated message is
run through the clue detector, and that output becomes the message's tags. The model's
own guesses are discarded. This is why the tags can be trusted.

**The detector is calibrated against human-labeled data.** `scripts/calibrate.py`
measures the detector against human-validated messages (currently ~82% agreement, with
per-clue precision and recall reported). A score you cannot calibrate is a score you
cannot trust.

**A human approves everything.** The review desk is the safety gate; generation is
offline, so the public never gets a live generator. The `security/` layer then
red-teams the pipeline itself (prompt injection, poisoned trend feed, data leakage,
misuse) with before-and-after evidence, mapped to the OWASP LLM and Agentic Top 10.

---

## Quick start (macOS)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# confirm the detector is calibrated against the validated data
python3 scripts/calibrate.py

# generate candidates (uses local Ollama if running; otherwise an offline fallback)
python3 scripts/run_evolution.py --audience adults --trend "Tech Support Scam" --theme Bank --complexity 1

# review, edit, approve, then export to the game
python3 -m streamlit run review/app.py

# red-team the pipeline and produce the findings report
python3 security/redteam.py
```

Force offline mode with `REELSMART_FAKE=1`. Pick the model with `REELSMART_MODEL`.

---

## Layout

```
reel_smart/
  core/        clue detector, generators, scorers, evolution loop, storage, export
  trends/      weighted trend feed (FTC/FBI/AARP sourced) + live fetcher
  review/      Streamlit review desk (the human-in-the-loop)
  security/    red-team harness, defenses, and runnable attack demos
  scripts/     run_evolution.py, calibrate.py
  tests/       detector and scorer tests
```

---

## Tech

Python, local LLMs via Ollama, Streamlit, scikit-learn, SQLite, GitHub Actions.

---

## Author

Fatemeh Azam — Software Engineer and applied security researcher.
[Portfolio](https://fatemehazam-crypto.github.io/fatemehazam.github.io/) · [LinkedIn](https://www.linkedin.com/in/fatemeh-azam-1a219b55)
