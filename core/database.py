"""
SQLite persistence.

Stores generated candidates, their scores, review status, the evolution
history (for the progress chart), and approved rounds ready for export to
the game. Clues and spans are stored as JSON blobs.
"""

import sqlite3
import json
from typing import List, Optional
from pathlib import Path

from config import DB_PATH
from core.models import PhishMessage, LegitMessage, EvolutionRecord, Clues


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS phish (
                id INTEGER PRIMARY KEY, username TEXT, avatar TEXT, content TEXT,
                link TEXT, clues TEXT, clue_spans TEXT, complexity INTEGER,
                audience TEXT, trend TEXT, theme TEXT, generation INTEGER,
                score REAL, score_breakdown TEXT, parent_ids TEXT,
                source TEXT, status TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS legit (
                id INTEGER, username TEXT, avatar TEXT, content TEXT, link TEXT,
                audience TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS evolution (
                id INTEGER PRIMARY KEY AUTOINCREMENT, trend TEXT, theme TEXT,
                generation INTEGER, best_score REAL, avg_score REAL,
                population_scores TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS approved_rounds (
                round_id INTEGER PRIMARY KEY AUTOINCREMENT, phish_id INTEGER,
                legit_a TEXT, legit_b TEXT, theme TEXT, complexity INTEGER,
                trend TEXT, audience TEXT, created_at TEXT
            );
            """)

    # ---- phish ----
    def save_phish(self, m: PhishMessage):
        with self._conn() as c:
            c.execute("""INSERT OR REPLACE INTO phish VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                m.id, m.username, m.avatar, m.content, m.link,
                json.dumps(m.clues.to_dict()), json.dumps(m.clue_spans),
                m.complexity, m.audience, m.trend, m.theme, m.generation,
                m.score, json.dumps(m.score_breakdown), json.dumps(m.parent_ids),
                m.source, m.status, m.created_at.isoformat(),
            ))

    def save_phish_batch(self, msgs: List[PhishMessage]):
        for m in msgs:
            self.save_phish(m)

    def _row_to_phish(self, r) -> PhishMessage:
        m = PhishMessage(
            id=r["id"], username=r["username"], avatar=r["avatar"],
            content=r["content"], link=r["link"] or "",
            clues=Clues.from_dict(json.loads(r["clues"])),
            complexity=r["complexity"], audience=r["audience"],
            trend=r["trend"], theme=r["theme"], generation=r["generation"],
            score=r["score"], source=r["source"], status=r["status"],
        )
        m.clue_spans = json.loads(r["clue_spans"] or "{}")
        m.score_breakdown = json.loads(r["score_breakdown"] or "{}")
        m.parent_ids = json.loads(r["parent_ids"] or "[]")
        return m

    def get_phish(self, pid: int) -> Optional[PhishMessage]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM phish WHERE id=?", (pid,)).fetchone()
            return self._row_to_phish(r) if r else None

    def candidates(self, status: str = "candidate") -> List[PhishMessage]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM phish WHERE status=? ORDER BY score DESC", (status,)
            ).fetchall()
            return [self._row_to_phish(r) for r in rows]

    def set_status(self, pid: int, status: str):
        with self._conn() as c:
            c.execute("UPDATE phish SET status=? WHERE id=?", (status, pid))

    def update_content(self, m: PhishMessage):
        """Persist an edited message (content/link/clues/spans)."""
        self.save_phish(m)

    # ---- evolution ----
    def save_evolution(self, rec: EvolutionRecord):
        with self._conn() as c:
            c.execute("""INSERT INTO evolution
                (trend,theme,generation,best_score,avg_score,population_scores,created_at)
                VALUES (?,?,?,?,?,?,?)""", (
                rec.trend, rec.theme, rec.generation, rec.best_score,
                rec.avg_score, json.dumps(rec.population_scores),
                rec.created_at.isoformat(),
            ))

    def evolution_history(self) -> List[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM evolution ORDER BY id").fetchall()
            return [dict(r) for r in rows]

    # ---- approved rounds ----
    def approve_round(self, phish: PhishMessage, legit_a: LegitMessage,
                      legit_b: LegitMessage):
        with self._conn() as c:
            c.execute("""INSERT INTO approved_rounds
                (phish_id,legit_a,legit_b,theme,complexity,trend,audience,created_at)
                VALUES (?,?,?,?,?,?,?,?)""", (
                phish.id, json.dumps(legit_a.to_dict()), json.dumps(legit_b.to_dict()),
                phish.theme, phish.complexity, phish.trend, phish.audience,
                phish.created_at.isoformat(),
            ))
        self.set_status(phish.id, "approved")

    def approved_rounds(self) -> List[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM approved_rounds ORDER BY round_id").fetchall()
            out = []
            for r in rows:
                phish = self.get_phish(r["phish_id"])
                out.append({
                    "round_id": r["round_id"],
                    "phish": phish.to_dict() if phish else None,
                    "legit": [json.loads(r["legit_a"]), json.loads(r["legit_b"])],
                    "theme": r["theme"], "complexity": r["complexity"],
                    "trend": r["trend"], "audience": r["audience"],
                })
            return out

    def next_phish_id(self) -> int:
        with self._conn() as c:
            r = c.execute("SELECT MAX(id) AS m FROM phish").fetchone()
            base = r["m"] or 0
            return max(base, 1000) + 1   # keep generated IDs clear of seed IDs
