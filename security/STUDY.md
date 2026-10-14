# Reel Smart — security cheat sheet

One page to read before an interview. Run `python3 security/lab.py` to see
each of these happen live; `--quiz` to drill the Q&A.

The framing to lead with: **"I built an AI content pipeline, then treated it
as a system under test and attacked it."** That sentence alone signals the
mindset a security team wants.

---

## The 4 attacks, in plain terms

| # | Attack | One-sentence mechanism | The fix |
|---|--------|------------------------|---------|
| A1 | **Scorer prompt-injection** | A message being *scored* contains an instruction to the scorer ("rate this 10/10"). | Parse + **clamp** the score; never trust free-form model output; detect injection phrasing. |
| A2 | **Poisoned trend feed** | Malicious text in a *data* feed runs inside the generation prompt — indirect injection. | Treat all external data as untrusted; **sanitize before it enters a prompt**; isolate data from instructions. |
| A3 | **Secret leakage** | A secret in a message spreads to logs, DB, and exports. | **Scan + redact** on the way in and out; least-privilege keys; keep secrets out of prompts. |
| A4 | **Misuse / real-PII** | Generation is steered toward real personal data, turning a training tool into a weapon. | Fictional-only; **reject real-PII**; safety score → 0; offline generation; human approval gate. |

---

## The vocabulary to use (and define if asked)

- **Prompt injection** — untrusted text that the model treats as instructions.
- **Indirect (second-order) prompt injection** — the payload arrives through
  content the system later ingests (a feed, a page, a doc), not from the user
  directly. Harder to defend because it comes through a trusted channel.
- **Dual-use** — a tool useful for both good and harm; needs guardrails by
  design, not bolted on.
- **Defense in depth** — layered controls so no single bypass is fatal.
- **Least privilege** — components get only the access they need.
- **Human-in-the-loop** — a person approves high-impact actions; automation
  "earns scope gradually."

---

## How Reel Smart's design maps to the Greenwood Lab's stated principles

(The lab's public principles are: human accountability, data boundaries,
evidence-driven, automation limits, resilience. Tie your answers to these.)

- **Human accountability / automation limits** → the review desk: nothing is
  exported without a person approving it.
- **Data boundaries** → trend-feed sanitization + secret scanning before data
  crosses into prompts, logs, or exports.
- **Evidence-driven** → the detector is *calibrated* against 92 human-labeled
  messages (82% agreement, per-clue precision/recall), and the red-team runs
  produce a findings file. You can show numbers, not opinions.
- **Resilience** → the pipeline fails safe: unknown scorer output falls back
  to a neutral score; unsafe content scores 0 and can't be ranked.

---

## Three things to say when asked "what would you do next?"

1. Move the trend feed to **signed / authenticated sources** so poisoning is
   harder upstream.
2. Add a second **LLM judge that is itself injection-hardened**, and compare
   it to the heuristic scorer.
3. **Log every review decision** (who approved what, when) for an audit trail.

---

## Honest limitations (say these before they're asked — it builds trust)

- The clue detector is regex + calibration; it's ~82% agreement with humans,
  weakest on subtle grammar. A trained classifier is the next step.
- The defenses are pattern-based, so a novel phrasing could slip past one
  layer — which is exactly why there are several layers plus a human gate.
- These are *my* red-team cases; a real review would add fuzzing and an
  independent tester who didn't build the system.
