# Reel Smart — OWASP mapping

How Reel Smart's security work maps onto the two OWASP lists interviewers
reference by number: the **OWASP Top 10 for LLM Applications (2025)** and the
**OWASP Top 10 for Agentic Applications (ASI01–ASI10)**.

The point of this file is twofold: show which real risks this system has and
how they're handled, and show honest reasoning about which list items do **not**
apply here. Knowing what's out of scope — and why — is as much a signal of
understanding as knowing what's in.

---

## What Reel Smart actually is, in risk terms

An LLM content pipeline that ingests a data feed (trends), generates text,
scores it automatically, and exports approved items. Generation is offline
(local model), and a human approves every export. That shape determines which
risks are real.

---

## OWASP Top 10 for LLM Applications (2025)

| ID | Risk | In Reel Smart? | How it's handled / why out of scope |
|----|------|----------------|-------------------------------------|
| **LLM01** | Prompt Injection | **Yes — primary** | Direct (a candidate message instructing the scorer) and indirect (a poisoned trend feed). Handled by input sanitization + treating scorer output as untrusted. See lab A1, A2. |
| **LLM02** | Sensitive Information Disclosure | **Yes** | Secret scanning + redaction before anything is stored or exported. See lab A3. |
| **LLM03** | Supply Chain Vulnerabilities | Partial | The local model and Python deps are the supply chain. Mitigated by pinning deps and running a known model locally; no third-party plugins. Would harden with signed model sources. |
| **LLM04** | Data and Model Poisoning | **Yes (data)** | The trend feed is untrusted data that reaches a prompt — poisoning vector. Sanitized before use. No fine-tuning, so model poisoning is out of scope by design. See lab A2. |
| **LLM05** | Improper Output Handling | **Yes** | Generated text flows into a DB, an export file, and the review UI. The UI escapes content; the detector re-runs on any edit; nothing is executed. This is the item worth adding a test for next. |
| **LLM06** | Excessive Agency | Out of scope | Reel Smart is a pipeline, not an autonomous agent — it has no tools, no ability to act on the world. The misuse guardrail (fiction-only, real-PII rejected) is the closest control. See lab A4. |
| **LLM07** | System Prompt Leakage | Low | Prompts contain no secrets — just task instructions and sanitized trend text. Nothing sensitive to leak. |
| **LLM08** | Vector and Embedding Weaknesses | Out of scope | No vector store or RAG in this system. |
| **LLM09** | Misinformation | Reframed | The system deliberately generates deceptive text — but as labeled training content, gated by human review, never presented as true. The safety scorer + review gate keep it on the training side. |
| **LLM10** | Unbounded Consumption | Low | Generation is a bounded local batch (fixed population × generations), not an open endpoint. No external API cost or DoS surface. |

**Covered with working code/tests:** LLM01, LLM02, LLM04 (data), and the
misuse angle of LLM09. **Honest next step:** a test for LLM05 (improper output
handling) — assert the review UI escapes a message containing HTML/script.

---

## OWASP Top 10 for Agentic Applications (ASI01–ASI10)

Reel Smart is mostly a pipeline, not a multi-agent system, so most of these are
out of scope — and saying so clearly is the right answer, not a gap.

| ID | Risk | In Reel Smart? | Note |
|----|------|----------------|------|
| **ASI01** | Agent Goal Hijack | **Yes (analogue)** | The scorer-injection attack is a goal-hijack of the scoring step. Same class, smaller surface. See lab A1. |
| **ASI02** | Tool Misuse and Exploitation | Out of scope | No tools wired to the model. |
| **ASI03** | Identity and Privilege Abuse | Out of scope | No credentials or privileged actions in the loop. |
| **ASI04** | Agentic Supply Chain | Partial | Same as LLM03 — local model + deps. |
| **ASI05** | Unexpected Code Execution | Out of scope | Generated text is never executed. |
| **ASI06** | Memory and Context Poisoning | **Yes (analogue)** | The trend feed is the closest thing to persistent context; poisoning it is handled by sanitization. See lab A2. |
| **ASI07** | Insecure Inter-Agent Communication | Out of scope | Single pipeline, not multiple communicating agents. |
| **ASI08** | Cascading Failures | Low | The evolution loop could amplify a bad score across generations — bounded by the human review gate at the end. |
| **ASI09** | Human-Agent Trust Exploitation | **Yes (by design)** | The whole product teaches people NOT to over-trust messages. The review gate also keeps a human skeptical of the generator's output. |
| **ASI10** | Rogue Agents | Out of scope | No autonomous agents to go rogue. |

---

## The one-sentence version (for an interview)

> "Reel Smart's real OWASP exposure is prompt injection (LLM01 / ASI01),
> sensitive-data disclosure (LLM02), data poisoning via the trend feed (LLM04 /
> ASI06), and improper output handling (LLM05). I built and tested defenses for
> the first three; output handling is my next test. The agentic risks mostly
> don't apply because it's a pipeline, not an autonomous agent — and being able
> to say *why* a risk is out of scope matters as much as handling the ones that
> are in."

Sources for the lists: OWASP GenAI Security Project — "Top 10 for LLM
Applications (2025)" and "Top 10 for Agentic Applications (ASI01–ASI10)".
