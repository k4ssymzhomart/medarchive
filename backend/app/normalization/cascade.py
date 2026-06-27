"""Каскад сопоставления одной позиции (раздел 8.2).

Уровни: 1 точное, 2 RapidFuzz, 3 эмбеддинги (pgvector), 4 реранкер,
5 LLM арбитр. Каждый следующий дороже и точнее. Деградация изящная:
без AI ключей работают уровни 1-2, демо не падает.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MatchMethod, Service
from app.normalization import embeddings as emb
from app.normalization import rerank as rr
from app.normalization.lexical import LexicalIndex
from app.normalization.llm_arbiter import arbitrate


@dataclass
class Candidate:
    service_id: uuid.UUID
    service_name: str
    score: float
    method: MatchMethod
    rank: int = 0


@dataclass
class MatchOutcome:
    service_id: uuid.UUID | None = None
    service_name: str | None = None
    score: float = 0.0
    method: MatchMethod = MatchMethod.none
    candidates: list[Candidate] = field(default_factory=list)
    note: str | None = None

    @property
    def is_auto(self) -> bool:
        return self.service_id is not None and self.score >= settings.match_high_threshold


class MatchCascade:
    def __init__(self, db: Session, lexical: LexicalIndex | None = None) -> None:
        self.db = db
        self.lexical = lexical or LexicalIndex.from_db(db)

    # --- уровень 3: семантический поиск в pgvector ---
    def _semantic(self, raw: str, category: str | None, top_k: int = 20) -> list[Candidate]:
        vector = emb.embed_text(self.db, raw)
        if vector is None:
            return []
        stmt = (
            select(Service, Service.embedding.cosine_distance(vector).label("dist"))
            .where(Service.is_active.is_(True), Service.embedding.is_not(None))
        )
        if category:
            stmt = stmt.where(Service.category == category)
        stmt = stmt.order_by("dist").limit(top_k)
        rows = self.db.execute(stmt).all()
        out: list[Candidate] = []
        for rank, (svc, dist) in enumerate(rows):
            score = max(0.0, 1.0 - float(dist))  # cosine distance -> similarity
            out.append(Candidate(svc.service_id, svc.service_name, score, MatchMethod.embedding, rank))
        return out

    def match(self, raw: str, category: str | None = None) -> MatchOutcome:
        # Уровень 1: точное совпадение.
        exact = self.lexical.exact(raw)
        if exact:
            return MatchOutcome(
                service_id=exact.service_id,
                service_name=exact.service_name,
                score=1.0,
                method=MatchMethod.exact,
                candidates=[Candidate(exact.service_id, exact.service_name, 1.0, MatchMethod.exact, 0)],
            )

        # Уровень 2: лексический RapidFuzz.
        lex = self.lexical.search(raw, limit=20, category=category)
        lex_cands = [
            Candidate(e.service_id, e.service_name, s, MatchMethod.fuzzy, i)
            for i, (e, s) in enumerate(lex)
        ]
        if lex_cands and lex_cands[0].score >= settings.rapidfuzz_auto_threshold:
            best = lex_cands[0]
            return MatchOutcome(best.service_id, best.service_name, best.score, MatchMethod.fuzzy, lex_cands)

        # Уровень 3: семантический (эмбеддинги).
        sem_cands = self._semantic(raw, category)

        # Слияние кандидатов лексики и семантики (берём максимум score по сервису).
        merged: dict[uuid.UUID, Candidate] = {}
        for c in lex_cands + sem_cands:
            cur = merged.get(c.service_id)
            if cur is None or c.score > cur.score:
                merged[c.service_id] = c
        candidates = sorted(merged.values(), key=lambda c: c.score, reverse=True)[:20]
        for i, c in enumerate(candidates):
            c.rank = i

        if not candidates:
            return MatchOutcome(method=MatchMethod.none, candidates=[])

        best = candidates[0]

        # Уровень 4: реранкер (только если есть семантика и достаточно кандидатов).
        if sem_cands and len(candidates) > 1:
            docs = [c.service_name for c in candidates]
            reranked = rr.rerank(self.db, raw, docs, top_n=len(docs))
            if reranked:
                for idx, score in reranked:
                    candidates[idx].score = max(candidates[idx].score, score)
                    candidates[idx].method = MatchMethod.rerank
                candidates.sort(key=lambda c: c.score, reverse=True)
                for i, c in enumerate(candidates):
                    c.rank = i
                best = candidates[0]

        # Авто, если уверенно.
        if best.score >= settings.match_high_threshold:
            return MatchOutcome(best.service_id, best.service_name, best.score, best.method, candidates)

        # Уровень 5: LLM арбитр для пограничной зоны.
        if settings.match_low_threshold <= best.score < settings.match_high_threshold:
            top3 = candidates[:3]
            verdict = arbitrate(self.db, raw, category, [c.service_name for c in top3])
            if verdict:
                choice = int(verdict.get("choice", 0))
                conf = float(verdict.get("confidence", 0.0))
                reason = verdict.get("reason")
                if 1 <= choice <= len(top3):
                    chosen = top3[choice - 1]
                    score = max(chosen.score, conf)
                    return MatchOutcome(
                        chosen.service_id, chosen.service_name, score,
                        MatchMethod.llm, candidates, note=reason,
                    )
                return MatchOutcome(
                    None, None, best.score, MatchMethod.none, candidates,
                    note=reason or "LLM: совпадения нет",
                )

        # Пограничная/низкая зона без авторешения -> возвращаем кандидатов для ревью.
        return MatchOutcome(None, None, best.score, MatchMethod.none, candidates)
