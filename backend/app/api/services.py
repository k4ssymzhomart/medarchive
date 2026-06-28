"""Эндпоинты справочника услуг (раздел 10)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Partner, PriceItem, Service
from app.schemas import (
    Page,
    ServiceListResponse,
    ServiceOut,
    ServicePartnerPrice,
)

router = APIRouter()


@router.get(
    "/services",
    response_model=ServiceListResponse,
    summary="Справочник услуг",
    description="Список активных услуг справочника с фильтрами по категории и подстроке названия.",
)
def list_services(
    category: str | None = Query(None),
    q: str | None = Query(None, description="Фильтр по подстроке названия"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ServiceListResponse:
    stmt = select(Service).where(Service.is_active.is_(True))
    count_stmt = select(func.count(Service.service_id)).where(Service.is_active.is_(True))
    if category:
        stmt = stmt.where(Service.category == category)
        count_stmt = count_stmt.where(Service.category == category)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Service.service_name.ilike(like))
        count_stmt = count_stmt.where(Service.service_name.ilike(like))

    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        stmt.order_by(Service.service_name).limit(limit).offset(offset)
    ).scalars().all()
    return ServiceListResponse(
        page=Page(total=total, limit=limit, offset=offset),
        items=[ServiceOut.model_validate(s) for s in rows],
    )


@router.get(
    "/services/{service_id}/partners",
    response_model=list[ServicePartnerPrice],
    summary="Партнёры по услуге",
    description="Кто оказывает услугу и по какой цене (только активные позиции, по возрастанию цены).",
    responses={404: {"description": "Услуга не найдена"}},
)
def service_partners(
    service_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[ServicePartnerPrice]:
    """Кто оказывает услугу и по какой цене."""
    if db.get(Service, service_id) is None:
        raise HTTPException(404, "Услуга не найдена")
    rows = db.execute(
        select(PriceItem, Partner)
        .join(Partner, Partner.partner_id == PriceItem.partner_id)
        .where(
            PriceItem.service_id == service_id,
            PriceItem.is_active.is_(True),
        )
        .order_by(PriceItem.price_resident_kzt.asc().nullslast())
    ).all()
    return [
        ServicePartnerPrice(
            partner_id=p.partner_id,
            partner_name=p.name,
            city=p.city,
            price_resident_kzt=it.price_resident_kzt,
            price_nonresident_kzt=it.price_nonresident_kzt,
            effective_date=it.effective_date,
            item_id=it.item_id,
        )
        for it, p in rows
    ]
