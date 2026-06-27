"""Эндпоинты партнёров и истории цен (раздел 10)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Partner, PriceDocument, PriceItem, Service
from app.schemas import (
    Page,
    PartnerListResponse,
    PartnerOut,
    PriceHistoryOut,
    PriceHistoryPoint,
    PriceItemListResponse,
    PriceItemOut,
)
from app.validation.versioning import pct_change

router = APIRouter()


@router.get("/partners", response_model=PartnerListResponse)
def list_partners(
    city: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PartnerListResponse:
    stmt = select(Partner)
    count_stmt = select(func.count(Partner.partner_id))
    if city:
        stmt = stmt.where(Partner.city == city)
        count_stmt = count_stmt.where(Partner.city == city)
    if is_active is not None:
        stmt = stmt.where(Partner.is_active.is_(is_active))
        count_stmt = count_stmt.where(Partner.is_active.is_(is_active))
    total = db.scalar(count_stmt) or 0
    rows = db.execute(stmt.order_by(Partner.name).limit(limit).offset(offset)).scalars().all()
    return PartnerListResponse(
        page=Page(total=total, limit=limit, offset=offset),
        items=[PartnerOut.model_validate(p) for p in rows],
    )


@router.get("/partners/{partner_id}/services", response_model=PriceItemListResponse)
def partner_services(
    partner_id: uuid.UUID,
    active_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PriceItemListResponse:
    """Весь прайс партнёра с ценами."""
    if db.get(Partner, partner_id) is None:
        raise HTTPException(404, "Партнёр не найден")
    stmt = select(PriceItem).where(PriceItem.partner_id == partner_id)
    count_stmt = select(func.count(PriceItem.item_id)).where(PriceItem.partner_id == partner_id)
    if active_only:
        stmt = stmt.where(PriceItem.is_active.is_(True))
        count_stmt = count_stmt.where(PriceItem.is_active.is_(True))
    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        stmt.order_by(PriceItem.service_name_raw).limit(limit).offset(offset)
    ).scalars().all()
    return PriceItemListResponse(
        page=Page(total=total, limit=limit, offset=offset),
        items=[PriceItemOut.model_validate(i) for i in rows],
    )


@router.get(
    "/partners/{partner_id}/services/{service_id}/history",
    response_model=PriceHistoryOut,
)
def price_history(
    partner_id: uuid.UUID,
    service_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> PriceHistoryOut:
    """История цен (наше расширение для демо версионирования, раздел 9.2)."""
    rows = db.execute(
        select(PriceItem, PriceDocument)
        .join(PriceDocument, PriceDocument.doc_id == PriceItem.doc_id)
        .where(
            PriceItem.partner_id == partner_id,
            PriceItem.service_id == service_id,
        )
        .order_by(PriceItem.effective_date.asc().nullsfirst())
    ).all()
    service = db.get(Service, service_id)

    points: list[PriceHistoryPoint] = []
    prev_price = None
    for it, doc in rows:
        price = it.price_resident_kzt or it.price_nonresident_kzt
        change = pct_change(prev_price, price)
        points.append(
            PriceHistoryPoint(
                item_id=it.item_id,
                effective_date=it.effective_date,
                price_resident_kzt=it.price_resident_kzt,
                price_nonresident_kzt=it.price_nonresident_kzt,
                is_active=it.is_active,
                document_name=doc.file_name,
                file_format=doc.file_format.value,
                pct_change=round(change, 4) if change is not None else None,
            )
        )
        if price is not None:
            prev_price = price

    return PriceHistoryOut(
        partner_id=partner_id,
        service_id=service_id,
        service_name=service.service_name if service else None,
        points=points,
    )
