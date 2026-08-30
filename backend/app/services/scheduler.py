from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories import job_repository, watchlist_repository


def enqueue_due_jobs(db: Session, reprocess_interval_hours: int, ingest_interval_hours: int) -> int:
    """Enqueues restrictive-list ingestion (singleton, one at a time) and one
    reprocess job per distinct watched CNPJ that's due. Returns how many were enqueued.
    """
    enqueued = 0

    ingest_cutoff = datetime.now(UTC) - timedelta(hours=ingest_interval_hours)
    if not job_repository.has_recent_or_pending(db, "ingest_restrictive_lists", ingest_cutoff):
        job_repository.enqueue(db, "ingest_restrictive_lists", {})
        enqueued += 1

    reprocess_cutoff = datetime.now(UTC) - timedelta(hours=reprocess_interval_hours)
    for cnpj in watchlist_repository.distinct_watched_cnpjs(db):
        if not job_repository.has_recent_or_pending(
            db, "reprocess_watchlist_entry", reprocess_cutoff, cnpj=cnpj
        ):
            job_repository.enqueue(db, "reprocess_watchlist_entry", {"cnpj": cnpj})
            enqueued += 1

    return enqueued
