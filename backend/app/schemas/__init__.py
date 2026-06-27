"""Pydantic схемы. Контракт API (OpenAPI) — единый источник правды для фронта."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Partner
# --------------------------------------------------------------------------- #
class PartnerOut(ORMModel):
    partner_id: uuid.UUID
    name: str
    city: str | None = None
    address: str | None = None
    bin: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    is_active: bool


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #
class ServiceOut(ORMModel):
    service_id: uuid.UUID
    service_name: str
    synonyms: list[str] = Field(default_factory=list)
    category: str | None = None
    icd_code: str | None = None
    is_active: bool


# --------------------------------------------------------------------------- #
# PriceItem
# --------------------------------------------------------------------------- #
class PriceItemOut(ORMModel):
    item_id: uuid.UUID
    doc_id: uuid.UUID
    partner_id: uuid.UUID
    service_id: uuid.UUID | None = None
    service_name_raw: str
    service_code_source: str | None = None
    price_resident_kzt: Decimal | None = None
    price_nonresident_kzt: Decimal | None = None
    price_original: Decimal | None = None
    currency_original: str
    is_verified: bool
    verification_note: str | None = None
    effective_date: date | None = None
    is_active: bool
    match_confidence: float | None = None
    match_method: str
    source_page: int | None = None
    source_row: int | None = None
    raw_price_label: str | None = None
    category: str | None = None
    needs_review: bool
    is_anomaly: bool


class MatchCandidateOut(ORMModel):
    service_id: uuid.UUID
    service_name: str = ""
    score: float
    method: str
    rank: int


class UnmatchedItemOut(PriceItemOut):
    """Несопоставленная/пограничная позиция с топ кандидатами и контекстом."""

    partner_name: str | None = None
    document_name: str | None = None
    candidates: list[MatchCandidateOut] = Field(default_factory=list)


class ServicePartnerPrice(BaseModel):
    """Кто оказывает услугу и по какой цене (GET /services/{id}/partners)."""

    partner_id: uuid.UUID
    partner_name: str
    city: str | None = None
    price_resident_kzt: Decimal | None = None
    price_nonresident_kzt: Decimal | None = None
    effective_date: date | None = None
    item_id: uuid.UUID


# --------------------------------------------------------------------------- #
# История цен (раздел 9.2)
# --------------------------------------------------------------------------- #
class PriceHistoryPoint(BaseModel):
    item_id: uuid.UUID
    effective_date: date | None = None
    price_resident_kzt: Decimal | None = None
    price_nonresident_kzt: Decimal | None = None
    is_active: bool
    document_name: str | None = None
    file_format: str | None = None
    pct_change: float | None = None  # к предыдущей версии


class PriceHistoryOut(BaseModel):
    partner_id: uuid.UUID
    service_id: uuid.UUID
    service_name: str | None = None
    points: list[PriceHistoryPoint] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Поиск
# --------------------------------------------------------------------------- #
class SearchResultItem(BaseModel):
    kind: str  # service | partner
    id: uuid.UUID
    title: str
    subtitle: str | None = None
    category: str | None = None
    rank: float = 0.0


class SearchResponse(BaseModel):
    query: str
    took_ms: float
    total: int
    results: list[SearchResultItem]


# --------------------------------------------------------------------------- #
# Match (ручное сопоставление, POST /match)
# --------------------------------------------------------------------------- #
class MatchRequest(BaseModel):
    item_id: uuid.UUID
    service_id: uuid.UUID | None = None  # None => «нет совпадения» / отклонить
    action: str = Field(default="confirm", pattern="^(confirm|reject|correct)$")
    note: str | None = None


class MatchResponse(BaseModel):
    item_id: uuid.UUID
    service_id: uuid.UUID | None = None
    match_method: str
    match_confidence: float | None = None
    is_verified: bool
    synonyms_learned: int = 0


# --------------------------------------------------------------------------- #
# Документы / загрузка
# --------------------------------------------------------------------------- #
class DocumentOut(ORMModel):
    doc_id: uuid.UUID
    partner_id: uuid.UUID | None = None
    file_name: str
    file_format: str
    effective_date: date | None = None
    parse_status: str
    parse_log: str | None = None
    page_count: int | None = None
    extractor_used: str | None = None
    ocr_applied: bool
    item_count: int
    processing_seconds: float | None = None
    parsed_at: datetime | None = None


class DocumentStatusOut(BaseModel):
    doc_id: uuid.UUID
    file_name: str
    parse_status: str
    item_count: int
    ocr_applied: bool
    processing_seconds: float | None = None
    parse_log: str | None = None


class UploadResponse(BaseModel):
    documents: list[DocumentOut]
    skipped_duplicates: list[str] = Field(default_factory=list)
    message: str


# --------------------------------------------------------------------------- #
# Статистика / отчёт о качестве (раздел 16)
# --------------------------------------------------------------------------- #
class FormatBreakdown(BaseModel):
    file_format: str
    documents: int
    items: int
    matched: int
    match_rate: float


class StatsResponse(BaseModel):
    documents_total: int
    documents_by_status: dict[str, int]
    items_total: int
    items_active: int
    items_matched: int
    match_rate: float  # главная цифра, цель > 0.70
    needs_review_count: int
    unmatched_count: int
    anomaly_count: int
    by_format: list[FormatBreakdown]
    by_partner: list[dict]
    avg_processing_seconds: float | None = None
    services_total: int
    partners_total: int


# --------------------------------------------------------------------------- #
# Пагинация
# --------------------------------------------------------------------------- #
class Page(BaseModel):
    total: int
    limit: int
    offset: int


class PartnerListResponse(BaseModel):
    page: Page
    items: list[PartnerOut]


class ServiceListResponse(BaseModel):
    page: Page
    items: list[ServiceOut]


class PriceItemListResponse(BaseModel):
    page: Page
    items: list[PriceItemOut]


class UnmatchedListResponse(BaseModel):
    page: Page
    items: list[UnmatchedItemOut]
