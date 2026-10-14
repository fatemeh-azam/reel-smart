#!/usr/bin/env python3
"""
OWASP study drill — all 20 items across the two lists interviewers cite:

  * OWASP Top 10 for LLM Applications (2025)      LLM01–LLM10
  * OWASP Top 10 for Agentic Applications         ASI01–ASI10

This is breadth practice to go alongside security/lab.py (which teaches four of
them in depth). Each item has: what it is, how you defend it, and whether it
applies to Reel Smart. Run it until you can give the "what / defense" for any
ID cold.

Run:
  python3 security/owasp_study.py              # LLM list, then agentic
  python3 security/owasp_study.py --llm        # just the LLM Top 10
  python3 security/owasp_study.py --agentic     # just the agentic Top 10
  python3 security/owasp_study.py --flash       # flashcard mode (ID -> you recall -> reveal)

Lists are the OWASP 2025 LLM Top 10 and the Agentic (ASI) Top 10. Always
confirm wording against the current owasp.org / genai.owasp.org pages.
"""

import argparse

# (id, name, what it is, how you defend it, reel smart relevance)
LLM = [
    ("LLM01", "Prompt Injection",
     "Crafted input makes the model follow attacker instructions, directly or indirectly (via content it ingests).",
     "Separate instructions from data; sanitize/validate inputs; constrain and check outputs; human review for high-impact actions.",
     "PRIMARY — scorer injection + poisoned trend feed (lab A1/A2)."),
    ("LLM02", "Sensitive Information Disclosure",
     "The model reveals confidential data — secrets, PII, proprietary info — in its output.",
     "Keep secrets out of prompts; scan/redact inputs and outputs; least-privilege data access; output filtering.",
     "YES — secret scanning + redaction (lab A3)."),
    ("LLM03", "Supply Chain Vulnerabilities",
     "Weak links in models, training data, plugins, or dependencies compromise the system.",
     "Vet and pin model + dependency sources; verify integrity; prefer signed/known-good components.",
     "PARTIAL — local model + pinned Python deps."),
    ("LLM04", "Data and Model Poisoning",
     "Manipulated training/fine-tuning or ingested data plants backdoors, bias, or bad behavior.",
     "Validate and sanitize data sources; isolate untrusted data from trusted instructions; no fine-tuning on unvetted data.",
     "YES (data) — the trend feed is an ingested-data poisoning vector (lab A2). No fine-tuning, so model poisoning is out of scope."),
    ("LLM05", "Improper Output Handling",
     "Downstream systems trust model output without checking it — leading to XSS, SSRF, SQLi, or code execution.",
     "Treat model output as untrusted: encode/escape it, validate before use, never pass it straight to a shell/DB/browser.",
     "YES — output goes to a DB, an export file, and the review UI. Next test to add."),
    ("LLM06", "Excessive Agency",
     "The model has too much functionality, permission, or autonomy and takes damaging actions.",
     "Least privilege for tools; require human approval for consequential actions; limit what the model can trigger.",
     "Out of scope — Reel Smart is a pipeline with no tools or actions. The review gate is the analogue."),
    ("LLM07", "System Prompt Leakage",
     "Secrets or sensitive logic embedded in the system prompt get exposed and reused by an attacker.",
     "Put no secrets in prompts; don't rely on prompt contents staying hidden; enforce controls outside the prompt.",
     "Low — prompts hold only task text + sanitized trend data."),
    ("LLM08", "Vector and Embedding Weaknesses",
     "Flaws in how embeddings are made/stored/retrieved enable injection, leakage, or manipulated retrieval.",
     "Secure the vector store; validate retrieved content; access controls on embeddings; watch for poisoned documents.",
     "Out of scope — no vector store / RAG."),
    ("LLM09", "Misinformation",
     "The model generates false or misleading content (hallucination) that users act on.",
     "Ground answers in sources; show provenance; human review; set user expectations about reliability.",
     "Reframed — Reel Smart generates deceptive text on purpose, but as labeled training content behind human review, never presented as true."),
    ("LLM10", "Unbounded Consumption",
     "Excessive inference (compute, memory, API calls) causes DoS, runaway cost, or degradation.",
     "Rate-limit and quota requests; cap output size and loops; monitor spend and latency.",
     "Low — bounded local batch, no open endpoint."),
]

ASI = [
    ("ASI01", "Agent Goal Hijack",
     "Malicious content redirects an agent toward objectives its operator never set.",
     "Validate inputs/goals; isolate untrusted content; constrain the agent's allowed objectives; monitor for drift.",
     "YES (analogue) — scorer-step hijack (lab A1)."),
    ("ASI02", "Tool Misuse and Exploitation",
     "An agent abuses tools it's allowed to use — bad parameters, chained calls — to cause harm.",
     "Least-privilege tools; validate tool parameters; sandbox; approve high-impact tool calls.",
     "Out of scope — no tools wired to the model."),
    ("ASI03", "Identity and Privilege Abuse",
     "An agent inherits or escalates privileged credentials and acts beyond its authority.",
     "Scoped, short-lived credentials per agent; no shared high-privilege identity; audit privileged actions.",
     "Out of scope — no credentials in the loop."),
    ("ASI04", "Agentic Supply Chain Vulnerabilities",
     "Compromised tools, plugins, or components the agent relies on introduce risk.",
     "Vet and pin components; verify integrity; limit what external components can do.",
     "Partial — same as LLM03."),
    ("ASI05", "Unexpected Code Execution",
     "An agent generates or runs code/commands unsafely, enabling RCE or data theft.",
     "Never exec model output; sandbox any code paths; allowlist commands; strong output validation.",
     "Out of scope — generated text is never executed."),
    ("ASI06", "Memory and Context Poisoning",
     "Attackers corrupt the agent's memory, embeddings, or RAG store, distorting later decisions.",
     "Validate what enters memory; isolate/expire untrusted context; integrity-check persistent state.",
     "YES (analogue) — the trend feed is the nearest persistent context; sanitized (lab A2)."),
    ("ASI07", "Insecure Inter-Agent Communication",
     "Messages between agents are spoofed or tampered with in a multi-agent system.",
     "Authenticate and sign inter-agent messages; validate their content; don't blindly trust a peer agent.",
     "Out of scope — single pipeline, not multiple agents."),
    ("ASI08", "Cascading Failures",
     "A small error propagates through planning, execution, and memory, compounding.",
     "Circuit breakers and limits; validate between stages; a human checkpoint before irreversible effects.",
     "Low — evolution loop is bounded by the final human review gate."),
    ("ASI09", "Human-Agent Trust Exploitation",
     "People over-trust agent output and get socially engineered through it.",
     "Show uncertainty and provenance; keep a human in the loop; design against blind trust.",
     "YES (by design) — the product teaches people NOT to over-trust messages; the review gate keeps the human skeptical."),
    ("ASI10", "Rogue Agents",
     "A compromised or misaligned agent causes harm while still looking legitimate.",
     "Monitor agent behavior; constrain scope; detect anomalies; kill-switch / revoke capability.",
     "Out of scope — no autonomous agents."),
]


def pause(label="Enter to reveal"):
    try:
        input(f"   [{label}] ")
    except EOFError:
        pass


def show_item(it, flash):
    id_, name, what, defense, reel = it
    print(f"\n{id_}  {name}")
    if flash:
        print("   (recall: what is it? how do you defend it?)")
        pause()
    print(f"   WHAT:    {what}")
    print(f"   DEFEND:  {defense}")
    print(f"   REEL:    {reel}")


def run(items, title, flash):
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)
    for it in items:
        show_item(it, flash)
        if flash:
            pause("Enter for next")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--agentic", action="store_true")
    ap.add_argument("--flash", action="store_true", help="recall before each reveal")
    args = ap.parse_args()

    do_llm = args.llm or not args.agentic
    do_asi = args.agentic or not args.llm

    print("\nOWASP study drill — say the WHAT and the DEFEND for each ID.")
    if do_llm:
        run(LLM, "OWASP Top 10 for LLM Applications (2025)", args.flash)
    if do_asi:
        run(ASI, "OWASP Top 10 for Agentic Applications (ASI)", args.flash)

    print("\n" + "=" * 72)
    print("  Goal: given any ID, give its WHAT + DEFEND in a sentence each.")
    print("  Then read security/OWASP_MAPPING.md for how the four you BUILT")
    print("  map onto these, and which items are out of scope for Reel Smart.")
    print("=" * 72)


if __name__ == "__main__":
    main()
