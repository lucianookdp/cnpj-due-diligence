import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Base


@pytest.fixture(scope="session")
def engine():
    """Runs against a dedicated "<database>_test" database, never the dev one.

    Deliberately separate from DATABASE_URL: this fixture calls
    create_all/drop_all around the whole test session, which would otherwise
    wipe out schema managed by Alembic migrations on the dev database. The
    "_test" database must already exist (see README setup instructions).
    Repository/service tests need real Postgres features (JSONB, recursive
    CTEs in later phases) that sqlite can't stand in for.
    """
    dev_url = make_url(get_settings().database_url)
    test_url = dev_url.set(database=f"{dev_url.database}_test")
    engine = create_engine(test_url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    # create_savepoint: code under test may call session.commit() (e.g. the
    # dossier service); that becomes a savepoint release instead of ending
    # the outer transaction, so the whole test still rolls back cleanly.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
