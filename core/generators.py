"""
Message generators.

Four strategies, all sharing one rule that fixes the original design:

  THE DETECTOR, NOT THE MODEL, SETS THE CLUE FLAGS.

Whatever clues an LLM claims in its JSON are discarded. Every generated
message is passed through ClueDetector, and the detector's output becomes
the message's clues + clue_spans. This is why the flags are trustworthy
and why the "QR clue not detecting" class of bug cannot happen here: the
clue is computed from the final text, once, in one place.

All generation goes through core.llm.chat(), which uses real Ollama when
available and a deterministic fake otherwise.
"""

import json
import random
from typing import List, Optional, Dict

from config import MODEL_TEMPERATURES, length_limit
from core.models import PhishMessage, Clues
from core.clues import ClueDetector
from core import llm


def _trim_words(text: str, max_words: int) -> str:
    """Safety net: hard-cap a message to max_words, ending on a sentence
    boundary where possible so trimmed output still reads cleanly."""
    words = text.split()
    if len(words) <= max_words:
        return text
    cut = " ".join(words[:max_words])
    # Prefer to end at the last sentence terminator within the cut.
    for end in (". ", "! ", "? "):
        idx = cut.rfind(end)
        if idx >= len(cut) * 0.5:   # don't trim away more than half
            return cut[:idx + 1].strip()
    return cut.strip() + "…"


def _length_clause(audience: str) -> str:
    lim = length_limit(audience)
    return (f" Keep it to about {lim['target_words']} words "
            f"(no more than {lim['max_words']}).")


def _extract_json(text: str) -> Optional[Dict]:
    start, end = text.find("{"), text.rfind("}") + 1
    if 0 <= start < end:
        try:
            return json.loads(text[start:end])
        except Exception:
            return None
    return None


def _avatar(theme: str) -> str:
    return f"res://avatars/{theme.lower().split()[0]}.png"


# Techniques whose whole point is that there is NO clickable link — the
# lure is a phone number, a QR code, or a human on the line. A link must
# never be attached to these, or the detector correctly flags a suspicious
# link the message doesn't actually contain.
NO_LINK_TRENDS = ("QR", "Quishing", "Voice", "Vishing", "Callback",
                  "Grandparent", "Tech Support", "Emergency")


def guess_link(theme: str, complexity: int, trend: str = "") -> str:
    """Pick a plausible link, or none when the technique uses no link."""
    if trend and any(k in trend for k in NO_LINK_TRENDS):
        return ""
    if complexity == 3 and random.random() < 0.4:
        return ""
    slug = theme.lower().replace(" ", "")
    return random.choice([
        f"https://{slug}-verify-now.com",
        f"https://secure-{slug}-update.com",
        f"http://{slug}-support.biz/verify",
    ])


class BaseGenerator:
    name = "base"

    def __init__(self):
        self.detector = ClueDetector()

    def _finalize(self, *, content: str, link: str, username: str,
                  theme: str, complexity: int, audience: str, trend: Optional[str],
                  message_id: int, generation: int, source: str,
                  parent_ids: Optional[List[int]] = None) -> Optional[PhishMessage]:
        """Build a PhishMessage with detector-authored clues."""
        content = (content or "").strip()
        if not content:
            return None
        # Enforce the length cap before anything else sees the text, so the
        # trimmed version is what gets scored, stored, and shown.
        content = _trim_words(content, length_limit(audience)["max_words"])
        clues, spans = self.detector.detect(content, link, username)
        return PhishMessage(
            id=message_id,
            username=username,
            avatar=_avatar(theme),
            content=content,
            link=link.strip() if link else "",
            clues=clues,
            clue_spans=spans,
            complexity=complexity,
            audience=audience,
            trend=trend,
            theme=theme,
            generation=generation,
            source=source,
            parent_ids=parent_ids or [],
        )

    def generate(self, **kw) -> Optional[PhishMessage]:
        raise NotImplementedError


class ConservativeGenerator(BaseGenerator):
    name = "conservative"

    def generate(self, *, theme, complexity, audience, trend, message_id,
                 generation, examples=None, **_) -> Optional[PhishMessage]:
        ex = ""
        if examples:
            e = random.choice(examples)
            ex = f"\nHere is an example of the right style:\n{e.content}\n"
        prompt = f"""You are writing a phishing message for an educational anti-phishing game.
Theme: {theme}. Audience: {audience}. Complexity: {complexity}/3 (1=obvious, 3=subtle).
Trend/technique to use: {trend}.{ex}
Write ONLY the message text. Use a fictional organization. Do not use real
personal data. Keep it realistic for the complexity level.{_length_clause(audience)}"""
        text = llm.chat(prompt, MODEL_TEMPERATURES["conservative"])
        data = _extract_json(text)
        content = data.get("content") if data else text
        link = guess_link(theme, complexity, trend)
        username = (data.get("username") if data else None) or f"{theme} Support"
        return self._finalize(content=content, link=link, username=username,
                               theme=theme, complexity=complexity, audience=audience,
                               trend=trend, message_id=message_id,
                               generation=generation, source="generated")



class CreativeGenerator(BaseGenerator):
    name = "creative"

    def generate(self, *, theme, complexity, audience, trend, message_id,
                 generation, **_) -> Optional[PhishMessage]:
        prompt = f"""Write a CREATIVE, unexpected phishing message for an educational game.
Theme: {theme}. Audience: {audience}. Complexity: {complexity}/3. Technique: {trend}.
Use a novel scenario or an unusual pretext. Fictional organization only, no real
personal data. Write ONLY the message text.{_length_clause(audience)}"""
        text = llm.chat(prompt, MODEL_TEMPERATURES["creative"])
        content = text
        link = guess_link(theme, complexity, trend)
        return self._finalize(content=content, link=link, username=f"{theme} Team",
                               theme=theme, complexity=complexity, audience=audience,
                               trend=trend, message_id=message_id,
                               generation=generation, source="generated")


class TrendFocusedGenerator(BaseGenerator):
    name = "trend_focused"

    def generate(self, *, theme, complexity, audience, trend, trend_desc,
                 message_id, generation, **_) -> Optional[PhishMessage]:
        prompt = f"""Write a phishing message that clearly demonstrates this technique:
{trend} — {trend_desc}
Theme: {theme}. Audience: {audience}. Complexity: {complexity}/3.
Fictional organization only, no real personal data. Write ONLY the message text.{_length_clause(audience)}"""
        content = llm.chat(prompt, MODEL_TEMPERATURES["trend_focused"])
        # The shared helper decides whether a link belongs for this technique.
        link = guess_link(theme, complexity, trend)
        return self._finalize(content=content, link=link, username=f"{theme} Security",
                               theme=theme, complexity=complexity, audience=audience,
                               trend=trend, message_id=message_id,
                               generation=generation, source="generated")


class MutatorGenerator(BaseGenerator):
    name = "mutator"

    def generate(self, *, theme, complexity, audience, trend, message_id,
                 generation, examples=None, **_) -> Optional[PhishMessage]:
        if not examples:
            return CreativeGenerator().generate(
                theme=theme, complexity=complexity, audience=audience, trend=trend,
                message_id=message_id, generation=generation)
        parent = random.choice(examples)
        knob = random.choice(["pretext", "urgency wording", "the channel", "the target detail"])
        prompt = f"""Improve this phishing message for an educational game by changing ONE thing: {knob}.
Keep the same theme ({theme}) and roughly the same length.
Original:
{parent.content}
Write ONLY the new message text. Fictional organization only, no real personal data."""
        content = llm.chat(prompt, MODEL_TEMPERATURES["mutator"])
        return self._finalize(content=content, link=parent.link, username=parent.username,
                               theme=theme, complexity=complexity, audience=audience,
                               trend=trend, message_id=message_id, generation=generation,
                               source="mutated", parent_ids=[parent.id])


class GeneratorOrchestrator:
    def __init__(self):
        self.generators = [
            ConservativeGenerator(), CreativeGenerator(),
            TrendFocusedGenerator(), MutatorGenerator(),
        ]

    def generate_population(self, *, theme, complexity, audience, trend, trend_desc,
                            population_size, start_id, generation, elite=None):
        pop: List[PhishMessage] = []
        elite = elite or []
        per = population_size // len(self.generators)
        rem = population_size % len(self.generators)
        for i, gen in enumerate(self.generators):
            count = per + (1 if i < rem else 0)
            for _ in range(count):
                mid = start_id + len(pop)
                examples = elite if gen.name in ("mutator", "conservative") else None
                msg = gen.generate(theme=theme, complexity=complexity, audience=audience,
                                   trend=trend, trend_desc=trend_desc, message_id=mid,
                                   generation=generation, examples=examples)
                if msg:
                    pop.append(msg)
        # Backfill if any generator returned None.
        while len(pop) < population_size:
            msg = CreativeGenerator().generate(
                theme=theme, complexity=complexity, audience=audience, trend=trend,
                message_id=start_id + len(pop), generation=generation)
            if msg:
                pop.append(msg)
            else:
                break
        return pop
