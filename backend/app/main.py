import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import assert_production_ready, get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
assert_production_ready(settings)

app = FastAPI(title="CNPJ Due Diligence API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: logs the full traceback server-side, but never
    leaks internals (a stack trace, a DB error message) to the client — that's
    both an information-disclosure risk and just a bad error message.
    FastAPI's own HTTPException handling still takes precedence over this;
    it only catches what nothing else did.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
