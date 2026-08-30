from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import ScheduledJob

# Single statement so the row lock is held only for the instant of the claim
# itself — no separate SELECT-then-UPDATE window for another worker to race.
# clock_timestamp() (real wall-clock time), not now()/CURRENT_TIMESTAMP (frozen
# at transaction start) — a scheduling check must see time actually advancing
# even within one long-running transaction.
#
# Also reclaims 'running' jobs stuck past stale_after_minutes: a worker that
# crashed or was killed mid-job otherwise leaves that row running forever,
# silently stalling that job type (e.g. restrictive-list refresh) for good.
_CLAIM_SQL = text("""
    UPDATE scheduled_jobs
    SET status = 'running', updated_at = clock_timestamp()
    WHERE id = (
        SELECT id FROM scheduled_jobs
        WHERE (status = 'pending' AND scheduled_for <= clock_timestamp())
           OR (status = 'running' AND updated_at < clock_timestamp() - make_interval(mins => :stale_after_minutes))
        ORDER BY scheduled_for
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id
""")


def enqueue(
    db: Session, job_type: str, payload: dict, scheduled_for: datetime | None = None
) -> ScheduledJob:
    job = ScheduledJob(
        job_type=job_type, payload=payload, scheduled_for=scheduled_for or datetime.now(UTC)
    )
    db.add(job)
    db.commit()
    return job


def claim_next(db: Session, stale_after_minutes: int = 30) -> ScheduledJob | None:
    result = db.execute(_CLAIM_SQL, {"stale_after_minutes": stale_after_minutes}).first()
    if result is None:
        return None
    db.commit()
    return db.query(ScheduledJob).filter(ScheduledJob.id == result[0]).one()


def mark_done(db: Session, job: ScheduledJob) -> None:
    job.status = "done"
    db.commit()


def mark_failed(db: Session, job: ScheduledJob, error: Exception) -> None:
    job.status = "failed"
    job.last_error = str(error)[:1000]
    job.attempts += 1
    db.commit()


def has_recent_or_pending(
    db: Session, job_type: str, cutoff: datetime, cnpj: str | None = None
) -> bool:
    query = db.query(ScheduledJob).filter(ScheduledJob.job_type == job_type)
    if cnpj is not None:
        query = query.filter(ScheduledJob.payload["cnpj"].astext == cnpj)

    active = query.filter(ScheduledJob.status.in_(["pending", "running"])).first()
    if active is not None:
        return True

    recent_done = query.filter(
        ScheduledJob.status == "done", ScheduledJob.updated_at >= cutoff
    ).first()
    return recent_done is not None
