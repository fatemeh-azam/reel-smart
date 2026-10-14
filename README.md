# Reel Smart

An AI system that generates **phishing-awareness training content** for an
educational game — and a security review of that AI system itself.

Reel Smart runs a *generate → score → evolve* loop with a local LLM to
produce realistic (but fictional) phishing messages, tags each with the
red-flag "clues" a learner should spot, and routes every candidate through
a **human review desk** before anything is exported to the game. Generation
runs entirely **offline** on your machine; only reviewed, approved content
ever leaves the desk.

It covers two audiences from one engine: the original **kids/family** set
and an added **adults / older-adults** tier (tech-support, Medicare,
grandparent-emergency, invoice, and vishing scams).

---

## Why it's built this way

Three design decisions are worth knowing up front, because they're the
difference between a demo and something trustworthy:

1. **The detector, not the model, authors the clue flags.** Every generated
   message is run through `core/clues.py`, and that output becomes the
   message's clues. The model's own guesses are discarded. This is why the
   clue tags can be trusted and why the old "QR clue not detecting" class of
   bug can't recur.

2. **The scorer is calibrated against human-validated data.** `scripts/
   calibrate.py` measures the detector against the 92 human-tagged seed
   messages. Current agreement: **~82%**, with per-clue precision/recall
   printed so you can see exactly where it's strong (links, urgency) and
   weak (subtle grammar). A score you can't calibrate is a score you can't
   trust.

3. **A human approves everything.** The review desk is the safety gate. The
   `security/` layer then red-teams the pipeline itself (prompt injection,
   poisoned trends, secret leakage, misuse) with before/after evidence.

---

## Quick start (macOS)

```bash
cd reel_smart
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Confirm the detector is calibrated against the validated data
python3 scripts/calibrate.py

# 2. Generate candidates (uses local Ollama if running; otherwise a
#    built-in offline fake so you can try everything without a model)
#    Start Ollama first for real output:  ollama serve
python3 scripts/run_evolution.py --audience adults \
    --trend "Tech Support Scam" --theme Bank --complexity 1

# 3. Review, edit, approve — then export to the game
streamlit run review/app.py

# 4. Red-team the pipeline and produce the findings report
python3 security/redteam.py
```

Force offline mode anytime with `REELSMART_FAKE=1`. Pick the model with
`REELSMART_MODEL=qwen2.5:14b` (the default).

**Message length.** The game shows short cards, so generated messages are
kept short: the prompt asks for a target word count and a hard trim is
applied after generation, with the effectiveness scorer penalizing anything
that runs long. Tune the caps per audience in `config.py` → `LENGTH_LIMITS`
(default: ~25 words for kids/family, ~45 for adults).

---

## Layout

```
reel_smart/
├── config.py            # all settings, clue + scoring definitions
├── core/
│   ├── clues.py         # clue detector — SOURCE OF TRUTH, returns spans
│   ├── models.py        # data models
│   ├── llm.py           # Ollama client + deterministic offline fallback
│   ├── generators.py    # 4 strategies; detector authors the clues
│   ├── scorers.py       # 6 scorers incl. calibratable effectiveness + safety
│   ├── evolution.py     # quality-diversity evolution loop
│   ├── seed.py          # loads + pairs the 92/184 validated messages
│   ├── database.py      # SQLite persistence
│   └── export.py        # approved rounds → game JSON
├── trends/              # weighted trend feed (FTC/FBI/AARP sourced)
├── review/app.py        # Streamlit review desk (human-in-the-loop)
├── security/            # red-team harness + defenses + report
├── scripts/             # run_evolution.py, calibrate.py
├── tests/               # pytest-style; also runnable directly
└── data/                # phish.json, legit.json, reel_smart.db (gitignored)
```

## Tests

```bash
python3 tests/test_clues.py      # 8 tests, pins the bug fixes
python3 tests/test_scorers.py    # 7 tests, scoring + defenses
```



