from app.models import ScheduledJob, User, WatchlistEntry
from app.repositories import job_repository
from app.services import scheduler


def _user(db) -> User:
    user = User(email="a@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    return user


def test_enqueues_ingest_job_when_none_exists(db):
    enqueued = scheduler.enqueue_due_jobs(db, reprocess_interval_hours=24, ingest_interval_hours=24)

    assert enqueued == 1
    assert db.query(ScheduledJob).filter_by(job_type="ingest_restrictive_lists").count() == 1


def test_does_not_double_enqueue_ingest_job(db):
    scheduler.enqueue_due_jobs(db, reprocess_interval_hours=24, ingest_interval_hours=24)

    scheduler.enqueue_due_jobs(db, reprocess_interval_hours=24, ingest_interval_hours=24)

    assert db.query(ScheduledJob).filter_by(job_type="ingest_restrictive_lists").count() == 1


def test_enqueues_reprocess_job_per_distinct_watched_cnpj(db):
    user = _user(db)
    db.add(WatchlistEntry(user_id=user.id, cnpj="11111111000111"))
    db.add(WatchlistEntry(user_id=user.id, cnpj="22222222000122"))
    db.flush()

    scheduler.enqueue_due_jobs(db, reprocess_interval_hours=24, ingest_interval_hours=24)

    reprocess_jobs = db.query(ScheduledJob).filter_by(job_type="reprocess_watchlist_entry").all()
    assert {j.payload["cnpj"] for j in reprocess_jobs} == {"11111111000111", "22222222000122"}


def test_does_not_double_enqueue_reprocess_job_for_same_cnpj(db):
    user = _user(db)
    db.add(WatchlistEntry(user_id=user.id, cnpj="11111111000111"))
    db.flush()

    scheduler.enqueue_due_jobs(db, reprocess_interval_hours=24, ingest_interval_hours=24)
    scheduler.enqueue_due_jobs(db, reprocess_interval_hours=24, ingest_interval_hours=24)

    reprocess_jobs = db.query(ScheduledJob).filter_by(job_type="reprocess_watchlist_entry").all()
    assert len(reprocess_jobs) == 1


def test_reenqueues_reprocess_job_once_previous_is_done_and_interval_passed(db):
    user = _user(db)
    db.add(WatchlistEntry(user_id=user.id, cnpj="11111111000111"))
    db.flush()

    scheduler.enqueue_due_jobs(db, reprocess_interval_hours=24, ingest_interval_hours=24)
    reprocess_job = db.query(ScheduledJob).filter_by(job_type="reprocess_watchlist_entry").one()
    job_repository.mark_done(db, reprocess_job)

    # interval_hours=0 means "always due" — simulates enough time having passed.
    scheduler.enqueue_due_jobs(db, reprocess_interval_hours=0, ingest_interval_hours=24)

    reprocess_jobs = db.query(ScheduledJob).filter_by(job_type="reprocess_watchlist_entry").all()
    assert len(reprocess_jobs) == 2
