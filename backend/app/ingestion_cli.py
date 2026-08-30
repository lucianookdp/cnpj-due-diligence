"""Runs the restrictive-list ingestion once. Usage: python -m app.ingestion_cli

Fase 5 will wire this into the scheduled job-queue worker; for now it's a
manually-run script.
"""

import logging

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.providers.lista_suja import ListaSujaProvider
from app.providers.portal_transparencia import PortalTransparenciaProvider
from app.services.restrictive_list_ingestion import ingest_all

logging.basicConfig(level=logging.INFO)


def main() -> None:
    settings = get_settings()
    portal = PortalTransparenciaProvider(
        settings.portal_transparencia_base_url,
        settings.portal_transparencia_api_key,
        settings.provider_timeout_seconds,
    )
    lista_suja = ListaSujaProvider(settings.lista_suja_pdf_url, settings.provider_timeout_seconds)

    with SessionLocal() as db:
        results = ingest_all(
            db,
            portal,
            lista_suja,
            settings.restrictive_list_max_pages,
            settings.restrictive_list_page_delay_seconds,
        )

    for list_type, count in results.items():
        print(f"{list_type}: {count} entries ingested")


if __name__ == "__main__":
    main()
