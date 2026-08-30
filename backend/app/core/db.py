from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # A request that raised partway through may have left uncommitted
        # changes staged — roll back explicitly rather than relying on the
        # connection pool to clean up an unclear state on close.
        db.rollback()
        raise
    finally:
        db.close()
