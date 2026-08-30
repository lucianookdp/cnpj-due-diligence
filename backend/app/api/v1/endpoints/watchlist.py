import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_resolver
from app.core.cnpj import InvalidCnpjError, normalize_cnpj
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.rate_limit import rate_limit
from app.models import Company, User, WatchlistEntry
from app.providers.resolver import ProviderResolver
from app.repositories import alert_repository, company_repository, watchlist_repository
from app.schemas.watchlist import AlertOut, WatchlistEntryCreate, WatchlistEntryOut
from app.services.dossier import DossierNotFoundError, ensure_company

router = APIRouter()


def _to_out(db: Session, entry: WatchlistEntry, company: Company | None) -> WatchlistEntryOut:
    alerts = alert_repository.list_for_company(db, company.id) if company else []
    return WatchlistEntryOut(
        id=entry.id,
        cnpj=entry.cnpj,
        label=entry.label,
        created_at=entry.created_at,
        razao_social=company.razao_social if company else None,
        situacao_cadastral=company.situacao_cadastral if company else None,
        recent_alerts=[
            AlertOut(alert_type=a.alert_type, message=a.message, detected_at=a.detected_at)
            for a in alerts[:10]
        ],
    )


@router.get("/watchlist", response_model=list[WatchlistEntryOut])
def list_watchlist(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[WatchlistEntryOut]:
    entries = watchlist_repository.list_for_user(db, current_user.id)
    return [_to_out(db, e, company_repository.get_by_cnpj(db, e.cnpj)) for e in entries]


@router.post(
    "/watchlist",
    response_model=WatchlistEntryOut,
    status_code=201,
    # Behind auth already, but still triggers a live provider fetch per call —
    # same cadence as the plain dossier lookup.
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60))],
)
def add_to_watchlist(
    payload: WatchlistEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    resolver: ProviderResolver = Depends(get_resolver),
) -> WatchlistEntryOut:
    try:
        normalized = normalize_cnpj(payload.cnpj)
    except InvalidCnpjError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if watchlist_repository.get_by_cnpj(db, current_user.id, normalized) is not None:
        raise HTTPException(status_code=409, detail="CNPJ já está na sua carteira")

    try:
        company = ensure_company(db, resolver, normalized, settings.cache_ttl_hours)
    except DossierNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"CNPJ {normalized} não encontrado") from exc

    entry = watchlist_repository.create(db, current_user.id, normalized, payload.label)
    return _to_out(db, entry, company)


@router.delete("/watchlist/{entry_id}", status_code=204)
def remove_from_watchlist(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    entry = watchlist_repository.get(db, entry_id, current_user.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Item não encontrado na carteira")
    watchlist_repository.delete(db, entry)
