import logging
import time

from sqlalchemy.orm import Session

from app.providers.base import ProviderError
from app.providers.lista_suja import ListaSujaProvider
from app.providers.lista_suja_schema import parse_row as parse_lista_suja_row
from app.providers.portal_transparencia import PortalTransparenciaProvider
from app.providers.portal_transparencia_schema import (
    parse_ceis_record,
    parse_cepim_record,
    parse_cnep_record,
    parse_leniencia_record,
)
from app.repositories import restrictive_list_repository

logger = logging.getLogger(__name__)

_API_LIST_PARSERS = {
    "ceis": parse_ceis_record,
    "cnep": parse_cnep_record,
    "cepim": parse_cepim_record,
}


def ingest_api_list(
    db: Session,
    provider: PortalTransparenciaProvider,
    list_type: str,
    max_pages: int,
    page_delay_seconds: float = 0.0,
) -> int:
    parser = _API_LIST_PARSERS[list_type]
    count = 0
    for pagina in range(1, max_pages + 1):
        records = provider.fetch_page(list_type, pagina)
        if not records:
            break
        for record in records:
            entry = parser(record)
            if entry is not None:
                restrictive_list_repository.upsert_entry(db, entry)
                count += 1
        db.commit()
        if page_delay_seconds:
            time.sleep(page_delay_seconds)
    return count


def ingest_leniencia(
    db: Session,
    provider: PortalTransparenciaProvider,
    max_pages: int,
    page_delay_seconds: float = 0.0,
) -> int:
    count = 0
    for pagina in range(1, max_pages + 1):
        records = provider.fetch_page("leniencia", pagina)
        if not records:
            break
        for record in records:
            for entry in parse_leniencia_record(record):
                restrictive_list_repository.upsert_entry(db, entry)
                count += 1
        db.commit()
        if page_delay_seconds:
            time.sleep(page_delay_seconds)
    return count


def ingest_lista_suja(db: Session, provider: ListaSujaProvider) -> int:
    count = 0
    for row in provider.fetch_raw_rows():
        entry = parse_lista_suja_row(row)
        if entry is not None:
            restrictive_list_repository.upsert_entry(db, entry)
            count += 1
    db.commit()
    return count


def ingest_all(
    db: Session,
    portal: PortalTransparenciaProvider,
    lista_suja: ListaSujaProvider,
    max_pages: int,
    page_delay_seconds: float = 0.2,
) -> dict[str, int]:
    """Runs every source independently — one source failing (e.g. the PDF
    changing shape, or the API key being rejected) must not block the others.

    page_delay_seconds paces requests to the CGU API — a full historical load
    is thousands of pages, and firing them back-to-back with no delay risks
    tripping their own rate limiting or getting our IP flagged, which would
    break this feature entirely rather than just slow it down.
    """
    results: dict[str, int] = {}

    for list_type in ("ceis", "cnep", "cepim"):
        try:
            results[list_type] = ingest_api_list(
                db, portal, list_type, max_pages, page_delay_seconds
            )
        except ProviderError:
            logger.exception("failed to ingest %s", list_type)
            results[list_type] = 0

    try:
        results["leniencia"] = ingest_leniencia(db, portal, max_pages, page_delay_seconds)
    except ProviderError:
        logger.exception("failed to ingest leniencia")
        results["leniencia"] = 0

    try:
        results["trabalho_escravo"] = ingest_lista_suja(db, lista_suja)
    except ProviderError:
        logger.exception("failed to ingest trabalho_escravo")
        results["trabalho_escravo"] = 0

    return results
