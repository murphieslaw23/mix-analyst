from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base (subclass form, required by the mypy plugin)."""


def get_db() -> Generator:
    """Dependency for obtaining database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize the database schema via Alembic migrations.

    Kept under this name so lifespan startup and existing test doubles
    keep working; new code should prefer
    api.app.db.migrations.upgrade_to_head directly.
    """
    from .migrations import upgrade_to_head

    upgrade_to_head()
