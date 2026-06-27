"""Версионирование цен и дедупликация (раздел 9.2, 9.3).

История = цепочка PriceItem с общими (partner_id, service_id), разными
effective_date, где у старых is_active=false и заполнен supersedes_item_id.
Ничего не удаляется (бессрочное хранение). Скачок цены > порога -> аномалия.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PriceItem


def _price_of(item: PriceItem) -> Decimal | None:
    """Цена для сравнения версий: первое заполненное поле, а не первое
    истинное (Decimal('0') ложен, поэтому ``or`` пропустил бы валидный ноль)."""
    for price in (item.price_resident_kzt, item.price_nonresident_kzt, item.price_original):
        if price is not None:
            return price
    return None


def pct_change(old: Decimal | None, new: Decimal | None) -> float | None:
    if old is None or new is None or old == 0:
        return None
    if not (old.is_finite() and new.is_finite()):
        return None
    return float(abs(new - old) / old)


def apply_versioning(db: Session, item: PriceItem) -> dict:
    """Связывает новую позицию с предыдущей версией для той же пары
    (партнёр, услуга). Архивирует старую, ставит флаг аномалии при скачке."""
    info = {"superseded": False, "anomaly": False, "pct_change": None, "duplicate": False}
    if item.service_id is None:
        return info

    # Предыдущие активные версии той же услуги у того же партнёра.
    prev_list = db.execute(
        select(PriceItem)
        .where(
            PriceItem.partner_id == item.partner_id,
            PriceItem.service_id == item.service_id,
            PriceItem.is_active.is_(True),
            PriceItem.item_id != item.item_id,
        )
        .order_by(PriceItem.effective_date.desc().nullslast())
    ).scalars().all()
    if not prev_list:
        return info

    prev = prev_list[0]

    # Дубликат: та же дата -> архивируем старую, оставляем новую (раздел 9.1).
    if prev.effective_date and item.effective_date and prev.effective_date == item.effective_date:
        info["duplicate"] = True

    new_price = _price_of(item)
    old_price = _price_of(prev)

    # Определяем порядок по дате: архивируем более старую.
    item_is_newer = True
    if item.effective_date and prev.effective_date:
        item_is_newer = item.effective_date >= prev.effective_date

    if item_is_newer:
        prev.is_active = False
        item.supersedes_item_id = prev.item_id
        info["superseded"] = True
        change = pct_change(old_price, new_price)
    else:
        item.is_active = False
        item.supersedes_item_id = prev.item_id
        change = pct_change(new_price, old_price)

    info["pct_change"] = change
    if change is not None and change > settings.anomaly_pct_threshold:
        item.is_anomaly = True
        item.needs_review = True
        info["anomaly"] = True
        note = f"Аномалия цены: изменение {change * 100:.0f}% между версиями"
        item.verification_note = (item.verification_note + "; " if item.verification_note else "") + note

    db.flush()
    return info
