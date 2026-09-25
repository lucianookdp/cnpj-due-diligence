import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import get_resolver
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.providers.lista_suja import ListaSujaProvider
from app.providers.portal_transparencia import PortalTransparenciaProvider
from app.providers.resolver import ProviderResolver
from app.services import federal_debt_import
from app.worker import run_once

router = APIRouter()


def _require_worker_secret(
    x_worker_secret: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    # Empty configured secret means the trigger is disabled, not "anything
    # goes" — comparing against "" would let a caller send no header at all.
    if not settings.worker_trigger_secret or not x_worker_secret:
        raise HTTPException(status_code=401, detail="Não autorizado")
    if not secrets.compare_digest(x_worker_secret, settings.worker_trigger_secret):
        raise HTTPException(status_code=401, detail="Não autorizado")


@router.post(
    "/internal/worker/run-once",
    dependencies=[Depends(_require_worker_secret)],
)
def run_worker_once(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    resolver: ProviderResolver = Depends(get_resolver),
) -> dict[str, int]:
    """Runs one worker pass (enqueue due jobs, drain the queue) and returns.

    Exists so a free external scheduler (a GitHub Actions cron workflow) can
    drive the same job-queue worker that `app/worker.py` polls continuously —
    Render's free plan doesn't offer an always-on background worker service.
    """
    portal = PortalTransparenciaProvider(
        settings.portal_transparencia_base_url,
        settings.portal_transparencia_api_key,
        settings.provider_timeout_seconds,
    )
    lista_suja = ListaSujaProvider(settings.lista_suja_pdf_url, settings.provider_timeout_seconds)
    processed = run_once(db, resolver, portal, lista_suja, settings)
    return {"processed": processed}


@router.get("/internal/pgfn/status", dependencies=[Depends(_require_worker_secret)])
def pgfn_status(db: Session = Depends(get_db)) -> dict:
    """Which PGFN quarter is loaded, so the refresh workflow can skip the
    multi-gigabyte download when nothing new has been published."""
    return federal_debt_import.status(db)


@router.post("/internal/pgfn/import", dependencies=[Depends(_require_worker_secret)])
async def pgfn_import(request: Request, db: Session = Depends(get_db)) -> dict:
    """Replaces the federal-debt table with a summary built by
    `python -m app.pgfn_file build` (see .github/workflows/pgfn-refresh.yml)."""
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > federal_debt_import.MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Resumo grande demais")
    try:
        reference, rows = await run_in_threadpool(federal_debt_import.parse_summary, bytes(body))
    except federal_debt_import.InvalidSummaryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    count = await run_in_threadpool(federal_debt_import.replace_all, db, rows)
    return {"reference": reference, "companies": count}
