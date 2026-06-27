"""Очереди оператора: unmatched и needs_review, ручное сопоставление (раздел 10, 9.4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Partner,
    PriceDocument,
    PriceItem,
    Service,
    ServiceMatchCandidate,
)
from app.normalization.match_service import manual_match
from app.schemas import (
    MatchCandidateOut,
    MatchRequest,
    MatchResponse,
    Page,
    UnmatchedItemOut,
    UnmatchedListResponse,
)

router = APIRouter()


def _candidates_for(db: Session, item_id) -> list[MatchCandidateOut]:
    rows = db.execute(
        select(ServiceMatchCandidate, Service.service_name)
        .join(Service, Service.service_id == ServiceMatchCandidate.service_id)
        .where(ServiceMatchCandidate.item_id == item_id)
        .order_by(ServiceMatchCandidate.rank)
    ).all()
    return [
        MatchCandidateOut(
            service_id=c.service_id,
            service_name=name,
            score=c.score,
            method=c.method.value,
            rank=c.rank,
        )
        for c, name in rows
    ]


@router.get(
    "/unmatched",
    response_model=UnmatchedListResponse,
    summary="Очередь оператора",
    description=(
        "Несопоставленные и пограничные позиции с топ-кандидатами справочника. "
        "mode: all | unmatched | needs_review | anomaly."
    ),
)
def list_unmatched(
    mode: str = Query("all", pattern="^(all|unmatched|needs_review|anomaly)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> UnmatchedListResponse:
    """Несопоставленные и пограничные позиции для операторов с топ кандидатами."""
    base = (
        select(PriceItem, Partner.name, PriceDocument.file_name)
        .join(Partner, Partner.partner_id == PriceItem.partner_id)
        .join(PriceDocument, PriceDocument.doc_id == PriceItem.doc_id)
        .where(PriceItem.is_active.is_(True))
    )
    count_stmt = select(func.count(PriceItem.item_id)).where(PriceItem.is_active.is_(True))

    if mode == "unmatched":
        cond = (PriceItem.service_id.is_(None)) & (PriceItem.needs_review.is_(False))
    elif mode == "needs_review":
        cond = PriceItem.needs_review.is_(True)
    elif mode == "anomaly":
        cond = PriceItem.is_anomaly.is_(True)
    else:
        cond = or_(PriceItem.service_id.is_(None), PriceItem.needs_review.is_(True))

    base = base.where(cond)
    count_stmt = count_stmt.where(cond)

    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        base.order_by(PriceItem.match_confidence.desc().nullslast()).limit(limit).offset(offset)
    ).all()

    items: list[UnmatchedItemOut] = []
    for it, partner_name, doc_name in rows:
        out = UnmatchedItemOut.model_validate(it)
        out.partner_name = partner_name
        out.document_name = doc_name
        out.candidates = _candidates_for(db, it.item_id)
        items.append(out)

    return UnmatchedListResponse(
        page=Page(total=total, limit=limit, offset=offset), items=items
    )


@router.post(
    "/match",
    response_model=MatchResponse,
    summary="Ручное сопоставление позиции",
    description="Подтвердить (confirm), отклонить (reject) или исправить (correct) сопоставление позиции.",
    responses={
        404: {"description": "Позиция или услуга не найдена"},
        422: {"description": "Некорректное действие или отсутствует service_id"},
    },
)
def match_endpoint(req: MatchRequest, db: Session = Depends(get_db)) -> MatchResponse:
    """Ручное сопоставление позиции (подтвердить/отклонить/исправить)."""
    try:
        result = manual_match(db, req.item_id, req.service_id, req.action, req.note)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return MatchResponse(**result)
