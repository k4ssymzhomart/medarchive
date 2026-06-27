"""Каскад сопоставления одной позиции (раздел 8.2).

Уровни: 1 точное, 2 RapidFuzz, 3 эмбеддинги (pgvector), 4 реранкер,
5 LLM арбитр. Каждый следующий дороже и точнее. Деградация изящная:
без AI ключей работают уровни 1-2, демо не падает.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MatchMethod, Service
from app.normalization import embeddings as emb
from app.normalization import rerank as rr
from app.normalization.lexical import LexicalIndex
from app.normalization.llm_arbiter import arbitrate
from app.normalization.normalize import normalize, normalize_code


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
    # Арбитр явно ВЫБРАЛ кандидата ("да") — это авто-матч, не ручная очередь.
    arbiter_yes: bool = False
    # Арбитр явно сказал "нет совпадения" — позиция неадресуема (вне знаменателя).
    arbiter_no: bool = False

    @property
    def is_auto(self) -> bool:
        # Авто, если уверенный детерминированный/лексический матч ИЛИ положительный
        # вердикт арбитра. Вердикт арбитра — это слой ТОЧНОСТИ, ему доверяем как авто.
        if self.service_id is None:
            return False
        return self.arbiter_yes or self.score >= settings.match_high_threshold


class MatchCascade:
    def __init__(self, db: Session, lexical: LexicalIndex | None = None) -> None:
        self.db = db
        self.lexical = lexical or LexicalIndex.from_db(db)

    # --- уровень 3: семантический поиск в pgvector ---
    def _semantic(self, raw: str, top_k: int | None = None) -> list[Candidate]:
        top_k = top_k or settings.embed_top_k
        # Задача C: НЕ фильтруем по категории. Таксономия справочника
        # (специальность) и раздела прайса разные, жёсткое равенство убивает recall.
        vector = emb.embed_text(self.db, raw)
        if vector is None:
            return []
        stmt = (
            select(Service, Service.embedding.cosine_distance(vector).label("dist"))
            .where(Service.is_active.is_(True), Service.embedding.is_not(None))
            .order_by("dist")
            .limit(top_k)
        )
        rows = self.db.execute(stmt).all()
        out: list[Candidate] = []
        for rank, (svc, dist) in enumerate(rows):
            score = max(0.0, 1.0 - float(dist))  # cosine distance -> similarity
            out.append(Candidate(svc.service_id, svc.service_name, score, MatchMethod.embedding, rank))
        return out

    # --- уровень 0: детерминированный матч по коду тарификатора ---
    def _match_by_code(self, raw: str, nc: str) -> MatchOutcome | None:
        hits = self.lexical.by_code(nc)
        if not hits:
            return None
        if len(hits) == 1:
            s = hits[0]
            return MatchOutcome(
                s.service_id, s.service_name, 0.98, MatchMethod.code,
                [Candidate(s.service_id, s.service_name, 0.98, MatchMethod.code, 0)],
            )
        # Неоднозначный код: дизамбигуируем текстом ТОЛЬКО среди hits.
        qn = normalize(raw)
        scored = sorted(
            ((fuzz.token_sort_ratio(qn, normalize(h.service_name)) / 100.0, h) for h in hits),
            key=lambda t: t[0],
            reverse=True,
        )
        candidates = [
            Candidate(h.service_id, h.service_name, max(0.95, sc) if i == 0 else sc, MatchMethod.code, i)
            for i, (sc, h) in enumerate(scored)
        ]
        best_sc, best_h = scored[0]
        return MatchOutcome(
            best_h.service_id, best_h.service_name, max(0.95, best_sc), MatchMethod.code, candidates
        )

    def match(self, raw: str, category: str | None = None, code: str | None = None) -> MatchOutcome:
        # Уровень 0: детерминированный матч по коду тарификатора (Задача B).
        # Самый надёжный путь, без AI. Идёт ПЕРЕД текстовым каскадом.
        nc = normalize_code(code)
        if nc:
            code_outcome = self._match_by_code(raw, nc)
            if code_outcome is not None:
                return code_outcome

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

        # Уровень 2: лексический RapidFuzz. Категорию НЕ передаём как фильтр (Задача C).
        lex = self.lexical.search(raw, limit=20, category=None)
        lex_cands = [
            Candidate(e.service_id, e.service_name, s, MatchMethod.fuzzy, i)
            for i, (e, s) in enumerate(lex)
        ]
        if lex_cands and lex_cands[0].score >= settings.rapidfuzz_auto_threshold:
            best = lex_cands[0]
            return MatchOutcome(best.service_id, best.service_name, best.score, MatchMethod.fuzzy, lex_cands)

        # Уровень 3: семантический (эмбеддинги). Можно выключить на ingest.
        sem_cands = self._semantic(raw) if settings.ai_matching_enabled else []

        # Слияние кандидатов лексики и семантики (берём максимум score по сервису).
        merged: dict[uuid.UUID, Candidate] = {}
        for c in lex_cands + sem_cands:
            cur = merged.get(c.service_id)
            if cur is None or c.score > cur.score:
                merged[c.service_id] = c
        candidates = sorted(merged.values(), key=lambda c: c.score, reverse=True)[
            : settings.candidate_pool
        ]
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

        # Уровень 5: LLM арбитр по ВСЕЙ полосе [match_low, match_high).
        # Полоса опущена до 0.40 — арбитр судит корректность кандидата, поэтому
        # точность держится; его "да" = авто-матч, "нет" = неадресуемо.
        if settings.match_low_threshold <= best.score < settings.match_high_threshold:
            topn = candidates[: settings.arbiter_candidates]
            verdict = arbitrate(self.db, raw, category, [c.service_name for c in topn])
            if verdict:
                choice = int(verdict.get("choice", 0))
                conf = float(verdict.get("confidence", 0.0))
                reason = verdict.get("reason")
                if 1 <= choice <= len(topn):
                    chosen = topn[choice - 1]
                    return MatchOutcome(
                        chosen.service_id, chosen.service_name, max(chosen.score, conf),
                        MatchMethod.llm, candidates, note=reason, arbiter_yes=True,
                    )
                return MatchOutcome(
                    None, None, best.score, MatchMethod.none, candidates,
                    note=reason or "Арбитр: совпадения в справочнике нет", arbiter_no=True,
                )

        # Пограничная/низкая зона без авторешения -> возвращаем кандидатов для ревью.
        return MatchOutcome(None, None, best.score, MatchMethod.none, candidates)
