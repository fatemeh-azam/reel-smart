"""
The evolution loop.

Generate -> score -> keep the best -> breed the next generation, repeating
until the score converges or MAX_GENERATIONS is hit. Two design choices
matter:

* QUALITY-DIVERSITY elitism. Instead of keeping only the single best
  message (which collapses the population onto one style), we keep the best
  message *per (complexity) cell*. This preserves coverage — the gap the
  data analysis flagged — rather than converging on one winner.
* The corpus passed to the creativity scorer grows every generation, so
  "novel" is measured against everything already produced, discouraging the
  loop from rediscovering the same message.

Everything is backend-agnostic (real Ollama or fake) via core.llm.
"""

from statistics import mean
from typing import List, Dict, Callable, Optional

from config import (POPULATION_SIZE, MAX_GENERATIONS, ELITE_KEEP,
                    CONVERGENCE_SCORE, CONVERGENCE_PATIENCE)
from core.models import PhishMessage, EvolutionRecord
from core.generators import GeneratorOrchestrator
from core.scorers import ScoringOrchestrator


def _elite_by_cell(scored: List[PhishMessage], keep: int) -> List[PhishMessage]:
    """Keep the top `keep` overall, plus the best of each complexity cell."""
    elite = list(scored[:keep])
    seen_ids = {m.id for m in elite}
    best_by_complexity: Dict[int, PhishMessage] = {}
    for m in scored:
        if m.complexity not in best_by_complexity:
            best_by_complexity[m.complexity] = m
    for m in best_by_complexity.values():
        if m.id not in seen_ids:
            elite.append(m)
            seen_ids.add(m.id)
    return elite


def run_evolution(*, trend: Dict, theme: str, complexity: int, audience: str,
                  seed_corpus: List[str], start_id: int,
                  on_generation: Optional[Callable] = None,
                  use_llm_effectiveness: bool = False):
    """
    Returns (best_message, all_scored_messages, evolution_records).
    on_generation(record, population) is called after each generation for
    live progress (used by the CLI and the review desk).
    """
    gen_orch = GeneratorOrchestrator()
    corpus = list(seed_corpus)
    records: List[EvolutionRecord] = []
    all_scored: List[PhishMessage] = []
    elite: List[PhishMessage] = []
    next_id = start_id
    best_score = -1.0
    stale = 0

    for generation in range(MAX_GENERATIONS):
        population = gen_orch.generate_population(
            theme=theme, complexity=complexity, audience=audience,
            trend=trend["name"], trend_desc=trend.get("description", ""),
            population_size=POPULATION_SIZE, start_id=next_id,
            generation=generation, elite=elite,
        )
        next_id += len(population)

        scorer = ScoringOrchestrator(corpus=corpus,
                                     use_llm_effectiveness=use_llm_effectiveness)
        scored = scorer.score_population(population)
        all_scored.extend(scored)
        corpus.extend(m.content for m in scored)

        gen_best = scored[0].score if scored else 0.0
        gen_avg = round(mean(m.score for m in scored), 2) if scored else 0.0
        rec = EvolutionRecord(
            trend=trend["name"], theme=theme, generation=generation,
            best_score=gen_best, avg_score=gen_avg,
            population_scores=[m.score for m in scored],
        )
        records.append(rec)
        if on_generation:
            on_generation(rec, scored)

        # Convergence check.
        if gen_best > best_score + 0.01:
            best_score = gen_best
            stale = 0
        else:
            stale += 1
        if gen_best >= CONVERGENCE_SCORE and stale >= CONVERGENCE_PATIENCE:
            break

        elite = _elite_by_cell(scored, ELITE_KEEP)

    all_scored.sort(key=lambda x: x.score, reverse=True)
    best = all_scored[0] if all_scored else None
    return best, all_scored, records
