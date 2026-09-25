from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.models import BatchCheck, User
from app.providers.base import CompanyNotFoundError
from app.services import batch_check
from tests.services.test_dossier import _raw


class _Resolver:
    """Found for most CNPJs, not found for one, and blows up for another."""

    def fetch_company(self, cnpj: str):
        if cnpj == "00000000000191":
            raise CompanyNotFoundError(cnpj)
        if cnpj == "99999999000191":
            raise RuntimeError("provider down")
        return _raw(cnpj)


def _user(db) -> User:
    user = User(email=f"u{datetime.now(UTC).timestamp()}@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    return user


def test_clean_cnpjs_normalizes_dedupes_and_drops_junk():
    assert batch_check.clean_cnpjs(
        ["11.222.333/0001-81", "11222333000181", "abc", "123", "33.000.167/0001-01"]
    ) == ["11222333000181", "33000167000101"]


def test_run_batch_records_each_outcome_and_finishes(db):
    batch = batch_check.create_batch(
        db, _user(db).id, ["11222333000181", "00000000000191", "99999999000191"]
    )

    batch_check.run_batch(db, _Resolver(), batch.id, get_settings(), pause_seconds=0)

    db.refresh(batch)
    assert batch.status == "done"
    assert [i.status for i in batch.items] == ["done", "not_found", "error"]
    done = batch.items[0]
    assert done.razao_social == "EMPRESA TESTE LTDA"
    assert done.score is not None


def test_only_one_batch_at_a_time_and_a_daily_cap(db):
    user = _user(db)
    batch_check.create_batch(db, user.id, ["11222333000181"])
    with pytest.raises(batch_check.BatchLimitError):
        batch_check.create_batch(db, user.id, ["11222333000181"])

    for batch in db.query(BatchCheck).filter(BatchCheck.user_id == user.id):
        batch.status = "done"
    for _ in range(batch_check.MAX_BATCHES_PER_DAY - 1):
        batch_check.create_batch(db, user.id, ["11222333000181"]).status = "done"
        db.commit()
    with pytest.raises(batch_check.BatchLimitError):
        batch_check.create_batch(db, user.id, ["11222333000181"])


def test_stalled_batch_is_closed_and_old_batches_expire(db):
    user = _user(db)
    batch = batch_check.create_batch(db, user.id, ["11222333000181"])
    batch.updated_at = datetime.now(UTC) - timedelta(hours=1)
    batch.created_at = datetime.now(UTC) - timedelta(days=batch_check.BATCH_RETENTION_DAYS + 1)
    db.commit()

    batch_check.close_if_stalled(db, batch)
    assert batch.status == "interrupted"

    assert batch_check.delete_expired(db) == 1
    assert db.query(BatchCheck).filter(BatchCheck.user_id == user.id).count() == 0
