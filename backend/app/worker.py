"""Long-running job-queue worker. Usage: python -m app.worker

Polls scheduled_jobs on an interval; each pass first enqueues whatever's due
(restrictive-list refresh, watchlist reprocessing) then drains the queue.
No separate scheduler process — a single worker does both, matching the
project's "no Redis/Celery" scale.
"""

import logging
import time

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import SessionLocal
from app.providers.lista_suja import ListaSujaProvider
from app.providers.portal_transparencia import PortalTransparenciaProvider
from app.providers.resolver import ProviderResolver, build_default_resolver
from app.repositories import job_repository
from app.services import reprocessing, scheduler
from app.services.restrictive_list_ingestion import ingest_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _handle_ingest_restrictive_lists(
    db: Session,
    _payload: dict,
    resolver: ProviderResolver,
    portal: PortalTransparenciaProvider,
    lista_suja: ListaSujaProvider,
    settings: Settings,
) -> None:
    results = ingest_all(
        db,
        portal,
        lista_suja,
        settings.restrictive_list_max_pages,
        settings.restrictive_list_page_delay_seconds,
    )
    logger.info("restrictive list ingestion: %s", results)


def _handle_reprocess_watchlist_entry(
    db: Session,
    payload: dict,
    resolver: ProviderResolver,
    _portal: PortalTransparenciaProvider,
    _lista_suja: ListaSujaProvider,
    _settings: Settings,
) -> None:
    alerts = reprocessing.reprocess_company(db, resolver, payload["cnpj"])
    logger.info("reprocessed %s: %d alert(s)", payload["cnpj"], len(alerts))


_HANDLERS = {
    "ingest_restrictive_lists": _handle_ingest_restrictive_lists,
    "reprocess_watchlist_entry": _handle_reprocess_watchlist_entry,
}


def run_once(
    db: Session,
    resolver: ProviderResolver,
    portal: PortalTransparenciaProvider,
    lista_suja: ListaSujaProvider,
    settings: Settings,
) -> int:
    scheduler.enqueue_due_jobs(
        db, settings.reprocess_interval_hours, settings.restrictive_list_ingest_interval_hours
    )

    processed = 0
    while True:
        job = job_repository.claim_next(db, settings.stale_job_minutes)
        if job is None:
            break
        try:
            _HANDLERS[job.job_type](db, job.payload, resolver, portal, lista_suja, settings)
            job_repository.mark_done(db, job)
        except Exception as exc:
            logger.exception("job %s (%s) failed", job.id, job.job_type)
            job_repository.mark_failed(db, job, exc)
        processed += 1
    return processed


def main() -> None:
    settings = get_settings()
    resolver = build_default_resolver(settings)
    portal = PortalTransparenciaProvider(
        settings.portal_transparencia_base_url,
        settings.portal_transparencia_api_key,
        settings.provider_timeout_seconds,
    )
    lista_suja = ListaSujaProvider(settings.lista_suja_pdf_url, settings.provider_timeout_seconds)

    logger.info("worker started, polling every %ds", settings.worker_poll_interval_seconds)
    while True:
        with SessionLocal() as db:
            processed = run_once(db, resolver, portal, lista_suja, settings)
        if processed:
            logger.info("processed %d job(s)", processed)
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
