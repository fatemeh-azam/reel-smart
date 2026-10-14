"""Data models for Reel Smart."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

from config import BASE_CLUES, EXTENDED_CLUES

ALL_CLUES = BASE_CLUES + EXTENDED_CLUES


@dataclass
class Clues:
    """Clue flags for a message. 1 = present, 0 = absent."""
    urgency: int = 0
    slink: int = 0
    bgrammer: int = 0
    tgoodtbt: int = 0
    pinfo: int = 0
    # Extended (technique-specific) clues
    suspiciousQR: int = 0
    callbackRequest: int = 0
    deviceCodeRequest: int = 0
    fakeInvoice: int = 0
    fakeCalendarEvent: int = 0
    urgentDeadline: int = 0
    spoofedSender: int = 0

    def to_dict(self) -> Dict:
        return {k: getattr(self, k) for k in ALL_CLUES}

    def base_dict(self) -> Dict:
        """Only the five base clues — what the game engine consumes."""
        return {k: getattr(self, k) for k in BASE_CLUES}

    def active(self) -> List[str]:
        return [k for k in ALL_CLUES if getattr(self, k) == 1]

    @classmethod
    def from_dict(cls, data: Dict) -> "Clues":
        return cls(**{k: int(data.get(k, 0) or 0) for k in ALL_CLUES})


@dataclass
class PhishMessage:
    """A generated or seed phishing message."""
    id: int
    username: str
    avatar: str
    content: str
    link: str
    clues: Clues
    complexity: int
    audience: str = "kids_family"
    trend: Optional[str] = None
    theme: Optional[str] = None
    generation: int = 0
    score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    # Spans that triggered each clue — {clue_name: [matched text, ...]}
    clue_spans: Dict[str, List[str]] = field(default_factory=dict)
    parent_ids: List[int] = field(default_factory=list)
    source: str = "seed"  # seed | generated | mutated | fake
    status: str = "candidate"  # candidate | approved | rejected
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "username": self.username,
            "avatar": self.avatar,
            "content": self.content,
            "link": self.link,
            "clues": self.clues.to_dict(),
            "complexity": self.complexity,
            "audience": self.audience,
            "trend": self.trend,
            "theme": self.theme,
            "generation": self.generation,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "clue_spans": self.clue_spans,
            "parent_ids": self.parent_ids,
            "source": self.source,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PhishMessage":
        return cls(
            id=data["id"],
            username=data["username"],
            avatar=data.get("avatar", ""),
            content=data["content"],
            link=data.get("link", ""),
            clues=Clues.from_dict(data.get("clues", {})),
            complexity=data.get("complexity", 2),
            audience=data.get("audience", "kids_family"),
            trend=data.get("trend"),
            theme=data.get("theme"),
            generation=data.get("generation", 0),
            score=data.get("score", 0.0),
            score_breakdown=data.get("score_breakdown", {}),
            clue_spans=data.get("clue_spans", {}),
            parent_ids=data.get("parent_ids", []),
            source=data.get("source", "seed"),
            status=data.get("status", "candidate"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data else datetime.now()
            ),
        )


@dataclass
class LegitMessage:
    """A legitimate (non-phish) message."""
    id: int
    username: str
    avatar: str
    content: str
    link: str
    audience: str = "kids_family"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "username": self.username,
            "avatar": self.avatar,
            "content": self.content,
            "link": self.link,
            "audience": self.audience,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LegitMessage":
        return cls(
            id=data["id"],
            username=data["username"],
            avatar=data.get("avatar", ""),
            content=data["content"],
            link=data.get("link", ""),
            audience=data.get("audience", "kids_family"),
        )


@dataclass
class EvolutionRecord:
    """One generation's summary, for the progress chart."""
    trend: str
    theme: str
    generation: int
    best_score: float
    avg_score: float
    population_scores: List[float]
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "trend": self.trend,
            "theme": self.theme,
            "generation": self.generation,
            "best_score": self.best_score,
            "avg_score": self.avg_score,
            "population_scores": self.population_scores,
            "created_at": self.created_at.isoformat(),
        }
