from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings - loaded from env vars / .env file."""

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DB_ECHO: bool = False

    # ── JWT ──────────────────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "AgentRAG.io"
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"

    # ── Encryption ───────────────────────────────────────────────────────────
    ENCRYPTION_KEY: str

    # ── Server ───────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # ── Streaming ────────────────────────────────────────────────────────────
    STREAM_TIMEOUT: int = 300
    HEARTBEAT_INTERVAL: int = 15
    MAX_RECONNECT_ATTEMPTS: int = 5
    BUFFER_SIZE: int = 1000

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60

    # ── OpenSearch Vector Store ───────────────────────────────────────────────
    OPENSEARCH_HOST: str = "localhost"
    OPENSEARCH_PORT: int = 9200
    OPENSEARCH_USER: Optional[str] = "admin"
    OPENSEARCH_PASSWORD: Optional[str] = "admin"
    OPENSEARCH_USE_SSL: bool = True
    OPENSEARCH_VERIFY_CERTS: bool = False
    # Embedding dimension MUST match the embedding model.
    # all-MiniLM-L6-v2  → 384
    # all-mpnet-base-v2 → 768
    OPENSEARCH_EMBEDDING_DIM: int = 384

    # ── Scheduler ─────────────────────────────────────────────────────────────
    SCHEDULER_POLL_SECONDS: int = 5
    SCHEDULER_MAX_CONCURRENCY: int = 2
    SCHEDULER_RUN_TIMEOUT_SECONDS: int = 1800
    SCHEDULER_STALE_SECONDS: int = 2100
    SCHEDULER_MIN_INTERVAL_MINUTES: int = 5
    SCHEDULER_HEARTBEAT_FILE: str = "/tmp/scheduler.heartbeat"

    # ── Notifications (platform SMTP) ─────────────────────────────────────────
    # Email notifications are disabled while SMTP_HOST (or the sender) is empty.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_STARTTLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_VERIFY_CERT: bool = True
    # Public URL of the UI, used to build links in notification emails
    APP_BASE_URL: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()