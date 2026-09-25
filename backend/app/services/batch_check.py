import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.cnpj import InvalidCnpjError, normalize_cnpj
from app.core.config import Settings
from app.core.db import SessionLocal
from app.models import BatchCheck, BatchCheckItem
from app.providers.resolver import ProviderResolver, build_default_resolver
from app.services.dossier import DossierNotFoundError, get_dossier

logger = logging.getLogger(__name__)

BATCH_RETENTION_DAYS = 30
MAX_BATCHES_PER_DAY = 10
# A batch still "processing" with no progress for this long lost its worker
# (a deploy or restart mid-run); it's closed instead of spinning forever.
STALLED_AFTER = timedelta(minutes=15)
# Pause between provider lookups: a batch shouldn't hammer the public APIs
# the single-CNPJ page also depends on.
_PAUSE_BETWEEN_LOOKUPS_SECONDS = 0.5


class BatchLimitError(Exception):
    pass


def clean_cnpjs(raw: list[str]) -> list[str]:
    """Normalized, de-duplicated, in the order given; malformed entries dropped."""
    seen: dict[str, None] = {}
    for value in raw:
        try:
            seen.setdefault(normalize_cnpj(value[:32]), None)
        except InvalidCnpjError:
            continue
    return list(seen)


def create_batch(db: Session, user_id: uuid.UUID, cnpjs: list[str]) -> BatchCheck:
    if (
        db.query(BatchCheck)
        .filter(BatchCheck.user_id == user_id, BatchCheck.status == "processing")
        .first()
        is not None
    ):
        raise BatchLimitError("Já existe uma checagem em lote em andamento. Aguarde terminar.")
    since = datetime.now(UTC) - timedelta(days=1)
    today = (
        db.query(BatchCheck)
        .filter(BatchCheck.user_id == user_id, BatchCheck.created_at >= since)
        .count()
    )
    if today >= MAX_BATCHES_PER_DAY:
        raise BatchLimitError(
            f"Limite de {MAX_BATCHES_PER_DAY} checagens em lote por dia atingido."
        )

    batch = BatchCheck(
        user_id=user_id,
        items=[BatchCheckItem(position=i, cnpj=cnpj) for i, cnpj in enumerate(cnpjs)],
    )
    db.add(batch)
    db.commit()
    return batch


def close_if_stalled(db: Session, batch: BatchCheck) -> None:
    updated = batch.updated_at if batch.updated_at.tzinfo else batch.updated_at.replace(tzinfo=UTC)
    if batch.status == "processing" and datetime.now(UTC) - updated > STALLED_AFTER:
        batch.status = "interrupted"
        db.commit()


def delete_expired(db: Session) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=BATCH_RETENTION_DAYS)
    count = db.query(BatchCheck).filter(BatchCheck.created_at < cutoff).delete()
    db.commit()
    return count


def _check_one(
    db: Session, resolver: ProviderResolver, item: BatchCheckItem, settings: Settings
) -> None:
    try:
        dossier = get_dossier(db, resolver, item.cnpj, settings.cache_ttl_hours)
    except DossierNotFoundError:
        item.status = "not_found"
        return
    item.status = "done"
    item.score = dossier.risk_score.score
    item.razao_social = dossier.razao_social[:255]
    item.situacao_cadastral = (dossier.situacao_cadastral or "")[:50]
    item.flags = [r.label for r in dossier.risk_score.results if r.triggered]


def run_batch(
    db: Session,
    resolver: ProviderResolver,
    batch_id: uuid.UUID,
    settings: Settings,
    pause_seconds: float = _PAUSE_BETWEEN_LOOKUPS_SECONDS,
) -> None:
    """One CNPJ at a time, committing each result so the page can show
    progress while it polls. A failed lookup marks that item and moves on."""
    batch = db.get(BatchCheck, batch_id)
    if batch is None:
        return
    for item in batch.items:
        if item.status != "pending":
            continue
        try:
            _check_one(db, resolver, item, settings)
        except Exception:
            logger.exception("batch %s: lookup for %s failed", batch_id, item.cnpj)
            db.rollback()
            item.status = "error"
        batch.updated_at = datetime.now(UTC)
        db.commit()
        time.sleep(pause_seconds)
    batch.status = "done"
    db.commit()


def process_batch(batch_id: uuid.UUID, settings: Settings) -> None:
    """Entry point for FastAPI BackgroundTasks: runs after the response is sent,
    on its own session, since the request's session is closed by then."""
    with SessionLocal() as db:
        run_batch(db, build_default_resolver(settings), batch_id, settings)
