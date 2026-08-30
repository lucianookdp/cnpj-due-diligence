from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_resolver
from app.core.cnpj import InvalidCnpjError, normalize_cnpj
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.rate_limit import rate_limit
from app.providers.resolver import ProviderResolver
from app.repositories import dossier_request_repository
from app.schemas.company import CompanyOut
from app.services.dossier import DossierNotFoundError, get_dossier
from app.services.pdf_export import render_dossier_pdf

router = APIRouter()


@router.get(
    "/companies/{cnpj}",
    response_model=CompanyOut,
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60))],
)
def read_company(
    cnpj: str,
    expected_activity_description: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    resolver: ProviderResolver = Depends(get_resolver),
) -> CompanyOut:
    try:
        normalized = normalize_cnpj(cnpj)
    except InvalidCnpjError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    dossier_request_repository.create(db, normalized, expected_activity_description)

    try:
        return get_dossier(
            db, resolver, normalized, settings.cache_ttl_hours, expected_activity_description
        )
    except DossierNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"CNPJ {normalized} não encontrado") from exc


@router.get(
    "/companies/{cnpj}/pdf",
    # Tighter than the plain dossier lookup — WeasyPrint rendering is real CPU
    # cost per request, not just a cached DB read.
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60))],
)
def read_company_pdf(
    cnpj: str,
    expected_activity_description: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    resolver: ProviderResolver = Depends(get_resolver),
) -> Response:
    try:
        normalized = normalize_cnpj(cnpj)
    except InvalidCnpjError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        company = get_dossier(
            db, resolver, normalized, settings.cache_ttl_hours, expected_activity_description
        )
    except DossierNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"CNPJ {normalized} não encontrado") from exc

    pdf_bytes = render_dossier_pdf(db, company, settings)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="dossie_{normalized}.pdf"'},
    )
