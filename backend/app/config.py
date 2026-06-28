"""Конфигурация из переменных окружения. Единый источник настроек."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- DB ---
    database_url: str = "postgresql+psycopg://medpartners:medpartners@localhost:5432/medpartners"

    @field_validator("database_url")
    @classmethod
    def _ensure_psycopg_driver(cls, v: str) -> str:
        """Облачные провайдеры (Render, Heroku) дают URL вида postgres:// или
        postgresql:// — у нас драйвер psycopg3. Приводим схему, чтобы строка из
        окружения работала без правок."""
        if v.startswith("postgresql+"):
            return v
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://"):]
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://"):]
        return v

    # --- Celery / Redis ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- Storage ---
    storage_backend: str = "local"  # local | s3
    storage_local_dir: str = "/data/storage"
    s3_endpoint_url: str = ""
    s3_bucket: str = "medpartners"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"

    # --- AI: embeddings ---
    embeddings_provider: str = "openai"
    openai_api_key: str = ""
    embeddings_model: str = "text-embedding-3-large"
    embeddings_dim: int = 3072

    # --- AI: rerank ---
    rerank_provider: str = "cohere"
    cohere_api_key: str = ""
    rerank_model: str = "rerank-v3.5"

    # --- AI: LLM арбитр ---
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-8"

    # --- Пороги нормализации (раздел 8.3) ---
    match_high_threshold: float = 0.85
    # Нижняя граница зоны арбитра. Опущена 0.60 -> 0.40: полоса 0.40-0.60 это
    # 52.7% позиций (смысл совпадает, слов нет) — главный резерв. Арбитр судит
    # КОРРЕКТНОСТЬ кандидата, поэтому точность держится, а не падает от порога.
    match_low_threshold: float = 0.40
    rapidfuzz_auto_threshold: float = 0.92
    # Recall: размер пула кандидатов эмбеддингов и итогового набора, который
    # видят реранк и арбитр. Чем больше, тем чаще истинный матч в наборе.
    embed_top_k: int = 45
    candidate_pool: int = 50
    # Сколько верхних кандидатов отдаём арбитру (было 3).
    arbiter_candidates: int = 5
    # AI-уровни каскада (эмбеддинги/реранк/арбитр). Выключаем на ingest для
    # быстрой загрузки, эмбеддинги греем пакетно, арбитра гоним отдельным rematch.
    ai_matching_enabled: bool = True

    # --- OCR ---
    ocr_languages: str = "rus+eng"
    ocr_dpi: int = 300

    # --- Аутентификация оператора (раздел 4.2) ---
    # Единый токен на админские эндпоинты (загрузка, сопоставление, очереди).
    # Пусто -> защита выключена (локальная разработка); в проде задаётся секретом.
    operator_token: str = ""

    # --- Прочее ---
    anomaly_pct_threshold: float = 0.50
    api_cors_origins: str = "http://localhost:5173,http://localhost:3000"
    fx_usd_kzt: float = 475.0
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        """Облачный AI доступен только при наличии хотя бы ключа эмбеддингов."""
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
