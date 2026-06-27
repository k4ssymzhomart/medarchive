"""SQLAlchemy модели. Схема из раздела 6, усиленная полями происхождения.

Все идентификаторы UUID. Все таблицы имеют created_at и updated_at.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base


# --------------------------------------------------------------------------- #
# Перечисления (enum). Совпадают с разделом 6.
# --------------------------------------------------------------------------- #
class FileFormat(str, enum.Enum):
    pdf = "pdf"
    docx = "docx"
    xlsx = "xlsx"
    xls = "xls"
    scan_pdf = "scan_pdf"


class ParseStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    error = "error"
    needs_review = "needs_review"


class Currency(str, enum.Enum):
    KZT = "KZT"
    USD = "USD"
    RUB = "RUB"


class MatchMethod(str, enum.Enum):
    code = "code"  # Level 0: детерминированный матч по коду тарификатора
    exact = "exact"
    synonym = "synonym"
    fuzzy = "fuzzy"
    embedding = "embedding"
    rerank = "rerank"
    llm = "llm"
    manual = "manual"
    none = "none"


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# --------------------------------------------------------------------------- #
# 6.1 Partner
# --------------------------------------------------------------------------- #
class Partner(Base, TimestampMixin):
    __tablename__ = "partners"

    partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    name_normalized: Mapped[str | None] = mapped_column(String(512), index=True)
    city: Mapped[str | None] = mapped_column(String(128))
    address: Mapped[str | None] = mapped_column(Text)
    bin: Mapped[str | None] = mapped_column(String(12), index=True)  # дедуп по БИН
    contact_email: Mapped[str | None] = mapped_column(String(256))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    documents: Mapped[list[PriceDocument]] = relationship(back_populates="partner")
    items: Mapped[list[PriceItem]] = relationship(back_populates="partner")


# --------------------------------------------------------------------------- #
# 6.2 PriceDocument
# --------------------------------------------------------------------------- #
class PriceDocument(Base, TimestampMixin):
    __tablename__ = "price_documents"

    doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partners.partner_id"), index=True
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_format: Mapped[FileFormat] = mapped_column(SAEnum(FileFormat), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1024))
    effective_date: Mapped[date | None] = mapped_column(Date, index=True)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parse_status: Mapped[ParseStatus] = mapped_column(
        SAEnum(ParseStatus), default=ParseStatus.pending, nullable=False, index=True
    )
    parse_log: Mapped[str | None] = mapped_column(Text)
    raw_content: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    extractor_used: Mapped[str | None] = mapped_column(String(64))
    ocr_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_seconds: Mapped[float | None] = mapped_column(Float)

    partner: Mapped[Partner | None] = relationship(back_populates="documents")
    items: Mapped[list[PriceItem]] = relationship(back_populates="document")


# --------------------------------------------------------------------------- #
# 6.4 Service (справочник)
# --------------------------------------------------------------------------- #
class Service(Base, TimestampMixin):
    __tablename__ = "services"

    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    service_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    service_name_normalized: Mapped[str | None] = mapped_column(String(512), index=True)
    synonyms: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    category: Mapped[str | None] = mapped_column(String(256), index=True)
    icd_code: Mapped[str | None] = mapped_column(String(32))
    embedding = mapped_column(Vector(settings.embeddings_dim), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    items: Mapped[list[PriceItem]] = relationship(back_populates="service")


# --------------------------------------------------------------------------- #
# 6.3 PriceItem (позиция прайса) + 6.6 версионирование через is_active/supersedes
# --------------------------------------------------------------------------- #
class PriceItem(Base, TimestampMixin):
    __tablename__ = "price_items"

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_documents.doc_id"), nullable=False, index=True
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partners.partner_id"), nullable=False, index=True
    )  # денормализовано для скорости
    service_name_raw: Mapped[str] = mapped_column(Text, nullable=False)
    service_code_source: Mapped[str | None] = mapped_column(String(128))
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.service_id"), index=True
    )

    price_resident_kzt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    price_nonresident_kzt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    price_original: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency_original: Mapped[Currency] = mapped_column(
        SAEnum(Currency), default=Currency.KZT, nullable=False
    )

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_note: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date | None] = mapped_column(Date, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    match_confidence: Mapped[float | None] = mapped_column(Float)
    match_method: Mapped[MatchMethod] = mapped_column(
        SAEnum(MatchMethod), default=MatchMethod.none, nullable=False
    )

    # Поля происхождения (раздел 7.8) — наше отличие.
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_row: Mapped[int | None] = mapped_column(Integer)
    raw_price_label: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(256))

    # 6.6 история: ссылка на предыдущую версию позиции.
    supersedes_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_items.item_id")
    )

    # Флаги валидации (раздел 9).
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    document: Mapped[PriceDocument] = relationship(back_populates="items")
    partner: Mapped[Partner] = relationship(back_populates="items")
    service: Mapped[Service | None] = relationship(back_populates="items")
    candidates: Mapped[list[ServiceMatchCandidate]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


# --------------------------------------------------------------------------- #
# 6.5 ServiceMatchCandidate (кандидаты сопоставления для очереди ревью)
# --------------------------------------------------------------------------- #
class ServiceMatchCandidate(Base, TimestampMixin):
    __tablename__ = "service_match_candidates"
    __table_args__ = (UniqueConstraint("item_id", "service_id", name="uq_candidate_item_service"),)

    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_items.item_id"), nullable=False, index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.service_id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[MatchMethod] = mapped_column(SAEnum(MatchMethod), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    item: Mapped[PriceItem] = relationship(back_populates="candidates")
    service: Mapped[Service] = relationship()


# --------------------------------------------------------------------------- #
# Кэш AI ответов (раздел 5.1): надёжность демо при сбое сети.
# --------------------------------------------------------------------------- #
class AICache(Base, TimestampMixin):
    __tablename__ = "ai_cache"

    cache_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # embedding | rerank | llm
    cache_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


__all__ = [
    "Base",
    "FileFormat",
    "ParseStatus",
    "Currency",
    "MatchMethod",
    "Partner",
    "PriceDocument",
    "Service",
    "PriceItem",
    "ServiceMatchCandidate",
    "AICache",
]
