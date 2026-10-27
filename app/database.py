from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# The engine is lazy: it only connects when the first query is executed.
# pool_pre_ping checks a pooled connection before use and replaces stale ones.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)

# expire_on_commit=False keeps loaded objects usable after commit() without
# triggering a new query for every attribute access.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield one session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
