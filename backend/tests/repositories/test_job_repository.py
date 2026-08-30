from datetime import UTC, datetime, timedelta

from app.repositories import job_repository


def test_enqueue_creates_pending_job(db):
    job = job_repository.enqueue(db, "ingest_restrictive_lists", {})

    assert job.status == "pending"
    assert job.job_type == "ingest_restrictive_lists"


def test_claim_next_returns_none_when_empty(db):
    assert job_repository.claim_next(db) is None


def test_claim_next_marks_job_as_running(db):
    job_repository.enqueue(db, "ingest_restrictive_lists", {})

    claimed = job_repository.claim_next(db)

    assert claimed is not None
    assert claimed.status == "running"


def test_claim_next_does_not_return_future_jobs(db):
    job_repository.enqueue(
        db, "ingest_restrictive_lists", {}, scheduled_for=datetime.now(UTC) + timedelta(hours=1)
    )

    assert job_repository.claim_next(db) is None


def test_claim_next_processes_in_scheduled_order(db):
    job_repository.enqueue(db, "a", {}, scheduled_for=datetime.now(UTC) - timedelta(minutes=5))
    job_repository.enqueue(db, "b", {}, scheduled_for=datetime.now(UTC) - timedelta(minutes=10))

    first = job_repository.claim_next(db)

    assert first.job_type == "b"


def test_claim_next_does_not_reclaim_running_job(db):
    job_repository.enqueue(db, "ingest_restrictive_lists", {})
    job_repository.claim_next(db)

    assert job_repository.claim_next(db) is None


def test_claim_next_reclaims_stale_running_job(db):
    job = job_repository.enqueue(db, "ingest_restrictive_lists", {})
    job_repository.claim_next(db)
    job.updated_at = datetime.now(UTC) - timedelta(minutes=60)
    db.flush()

    reclaimed = job_repository.claim_next(db, stale_after_minutes=30)

    assert reclaimed is not None
    assert reclaimed.id == job.id


def test_claim_next_does_not_reclaim_recently_running_job(db):
    job_repository.enqueue(db, "ingest_restrictive_lists", {})
    job_repository.claim_next(db)

    assert job_repository.claim_next(db, stale_after_minutes=30) is None


def test_mark_done(db):
    job = job_repository.enqueue(db, "ingest_restrictive_lists", {})
    job_repository.claim_next(db)

    job_repository.mark_done(db, job)

    assert job.status == "done"


def test_mark_failed_records_error_and_increments_attempts(db):
    job = job_repository.enqueue(db, "ingest_restrictive_lists", {})
    job_repository.claim_next(db)

    job_repository.mark_failed(db, job, ValueError("boom"))

    assert job.status == "failed"
    assert "boom" in job.last_error
    assert job.attempts == 1


def test_has_recent_or_pending_true_for_pending_job(db):
    job_repository.enqueue(db, "ingest_restrictive_lists", {})

    assert job_repository.has_recent_or_pending(
        db, "ingest_restrictive_lists", datetime.now(UTC) - timedelta(hours=24)
    )


def test_has_recent_or_pending_true_for_recent_done_job(db):
    job = job_repository.enqueue(db, "ingest_restrictive_lists", {})
    job_repository.claim_next(db)
    job_repository.mark_done(db, job)

    assert job_repository.has_recent_or_pending(
        db, "ingest_restrictive_lists", datetime.now(UTC) - timedelta(hours=24)
    )


def test_has_recent_or_pending_false_when_none_exist(db):
    assert not job_repository.has_recent_or_pending(
        db, "ingest_restrictive_lists", datetime.now(UTC) - timedelta(hours=24)
    )


def test_has_recent_or_pending_respects_cnpj_filter(db):
    job_repository.enqueue(db, "reprocess_watchlist_entry", {"cnpj": "11111111000111"})

    assert job_repository.has_recent_or_pending(
        db,
        "reprocess_watchlist_entry",
        datetime.now(UTC) - timedelta(hours=24),
        cnpj="11111111000111",
    )
    assert not job_repository.has_recent_or_pending(
        db,
        "reprocess_watchlist_entry",
        datetime.now(UTC) - timedelta(hours=24),
        cnpj="22222222000122",
    )
