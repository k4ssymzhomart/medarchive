"""Метрики качества (раздел 16). Живой дашборд = отчёт о качестве."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Partner,
    PriceDocument,
    PriceItem,
    Service,
)
from app.schemas import FormatBreakdown, StatsResponse


def build_stats(db: Session) -> StatsResponse:
    documents_total = db.scalar(select(func.count(PriceDocument.doc_id))) or 0

    status_rows = db.execute(
        select(PriceDocument.parse_status, func.count()).group_by(PriceDocument.parse_status)
    ).all()
    by_status = {s.value: c for s, c in status_rows}

    items_total = db.scalar(select(func.count(PriceItem.item_id))) or 0
    items_active = db.scalar(
        select(func.count(PriceItem.item_id)).where(PriceItem.is_active.is_(True))
    ) or 0
    items_matched = db.scalar(
        select(func.count(PriceItem.item_id)).where(
            PriceItem.is_active.is_(True), PriceItem.service_id.is_not(None)
        )
    ) or 0
    needs_review = db.scalar(
        select(func.count(PriceItem.item_id)).where(
            PriceItem.is_active.is_(True), PriceItem.needs_review.is_(True)
        )
    ) or 0
    unmatched = db.scalar(
        select(func.count(PriceItem.item_id)).where(
            PriceItem.is_active.is_(True),
            PriceItem.service_id.is_(None),
            PriceItem.needs_review.is_(False),
        )
    ) or 0
    anomalies = db.scalar(
        select(func.count(PriceItem.item_id)).where(PriceItem.is_anomaly.is_(True))
    ) or 0

    match_rate = (items_matched / items_active) if items_active else 0.0

    # Разбивка по форматам (раздел 16: справились с тяжёлыми сканами).
    fmt_rows = db.execute(
        select(
            PriceDocument.file_format,
            func.count(func.distinct(PriceDocument.doc_id)),
            func.count(PriceItem.item_id),
            func.count(PriceItem.service_id),
        )
        .select_from(PriceDocument)
        .outerjoin(
            PriceItem,
            (PriceItem.doc_id == PriceDocument.doc_id) & (PriceItem.is_active.is_(True)),
        )
        .group_by(PriceDocument.file_format)
    ).all()
    by_format = []
    for fmt, docs, items, matched in fmt_rows:
        by_format.append(
            FormatBreakdown(
                file_format=fmt.value,
                documents=docs,
                items=items,
                matched=matched,
                match_rate=round((matched / items), 4) if items else 0.0,
            )
        )

    # По партнёрам.
    part_rows = db.execute(
        select(
            Partner.name,
            func.count(PriceItem.item_id),
            func.count(PriceItem.service_id),
        )
        .select_from(Partner)
        .outerjoin(
            PriceItem,
            (PriceItem.partner_id == Partner.partner_id) & (PriceItem.is_active.is_(True)),
        )
        .group_by(Partner.name)
        .order_by(Partner.name)
    ).all()
    by_partner = [
        {
            "partner": name,
            "items": items,
            "matched": matched,
            "match_rate": round((matched / items), 4) if items else 0.0,
        }
        for name, items, matched in part_rows
    ]

    avg_seconds = db.scalar(
        select(func.avg(PriceDocument.processing_seconds)).where(
            PriceDocument.processing_seconds.is_not(None)
        )
    )

    services_total = db.scalar(select(func.count(Service.service_id))) or 0
    partners_total = db.scalar(select(func.count(Partner.partner_id))) or 0

    return StatsResponse(
        documents_total=documents_total,
        documents_by_status=by_status,
        items_total=items_total,
        items_active=items_active,
        items_matched=items_matched,
        match_rate=round(match_rate, 4),
        needs_review_count=needs_review,
        unmatched_count=unmatched,
        anomaly_count=anomalies,
        by_format=by_format,
        by_partner=by_partner,
        avg_processing_seconds=round(float(avg_seconds), 2) if avg_seconds else None,
        services_total=services_total,
        partners_total=partners_total,
    )
