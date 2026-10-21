from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import get_settings

settings = get_settings()

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release. create_all() never alters existing tables,
# so they are added idempotently at startup (alembic is not wired in this project).
_ADDED_COLUMNS = (
    ("messages", "verification", "JSON"),
    ("rag_messages", "verification", "JSON"),
)


def ensure_columns(bind=None) -> None:
    """Idempotent ADD COLUMN for _ADDED_COLUMNS (PostgreSQL only; no-op elsewhere)."""
    from sqlalchemy import inspect, text

    bind = bind or engine
    if bind.dialect.name != "postgresql":
        return
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    with bind.begin() as conn:
        for table, column, ddl_type in _ADDED_COLUMNS:
            if table not in existing_tables:
                continue
            if column in {c["name"] for c in inspector.get_columns(table)}:
                continue
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {ddl_type}'))


def init_db():
    """
    Initialize database tables
    """
    Base.metadata.create_all(bind=engine)
    ensure_columns()