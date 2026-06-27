"""Партнёры: резолв и дедупликация (раздел 6.1).

Имена клиник обезличены как «Клиника N». Дедуп по BIN, при отсутствии —
по нормализованному имени плюс город.
"""

from __future__ import annotations

import os
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Partner
from app.normalization.normalize import normalize_name

CLINIC_RE = re.compile(r"(Клиника\s*\d+)", re.IGNORECASE)


def partner_name_from_filename(file_name: str) -> str:
    base = os.path.basename(file_name)
    m = CLINIC_RE.search(base)
    if m:
        return m.group(1).strip().capitalize()
    return os.path.splitext(base)[0].strip()


def resolve_partner(
    db: Session,
    file_name: str,
    *,
    bin: str | None = None,
    city: str | None = None,
) -> Partner:
    name = partner_name_from_filename(file_name)
    norm = normalize_name(name)

    if bin:
        existing = db.execute(select(Partner).where(Partner.bin == bin)).scalar_one_or_none()
        if existing:
            return existing

    existing = db.execute(
        select(Partner).where(Partner.name_normalized == norm)
    ).scalar_one_or_none()
    if existing:
        return existing

    partner = Partner(name=name, name_normalized=norm, bin=bin, city=city, is_active=True)
    db.add(partner)
    db.flush()
    return partner
