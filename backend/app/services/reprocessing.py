from sqlalchemy.orm import Session

from app.models import Alert
from app.providers.resolver import ProviderResolver
from app.repositories import alert_repository, company_repository
from app.services import monitoring


def reprocess_company(db: Session, resolver: ProviderResolver, cnpj: str) -> list[Alert]:
    """Force-refetches cnpj (bypassing the normal dossier cache — that's the point of a
    scheduled reprocess) and persists an Alert for every change detected since the last run.

    Returns an empty list on a company's first-ever reprocess (nothing to diff against yet).
    """
    existing = company_repository.get_by_cnpj(db, cnpj)
    before = monitoring.snapshot(db, existing) if existing is not None else None

    raw = resolver.fetch_company(cnpj)
    company = company_repository.upsert_from_provider(db, raw)
    db.commit()

    if before is None:
        return []

    after = monitoring.snapshot(db, company)
    alerts = [
        alert_repository.create(db, company.id, alert_type, message)
        for alert_type, message in monitoring.detect_changes(before, after)
    ]
    db.commit()
    return alerts
