from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # development | production — gates the SECRET_KEY fail-fast check below.
    environment: str = "development"

    database_url: str = "postgresql+psycopg://cnpj:cnpj@localhost:5432/cnpj_due_diligence"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        # Managed Postgres providers (Render, Railway, etc.) hand out a plain
        # postgresql:// connection string — SQLAlchemy needs the +psycopg
        # driver marker to use psycopg3 instead of defaulting to psycopg2.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    cors_allowed_origins: list[str] = ["http://localhost:5173"]

    minha_receita_base_url: str = "https://minhareceita.org"
    brasil_api_base_url: str = "https://brasilapi.com.br/api"
    grafo_minha_receita_base_url: str = "https://grafo.minhareceita.org"
    provider_timeout_seconds: float = 10.0

    cache_ttl_hours: int = 720

    graph_max_depth: int = 2
    graph_max_nodes_per_level: int = 50
    # Bounds grafo.minhareceita.org reverse-lookup calls per company expansion —
    # a company with dozens of officers (common for large S.A.s) would otherwise
    # trigger one reverse-lookup call per officer.
    graph_max_partner_lookups_per_company: int = 20
    shared_address_threshold: int = 5

    portal_transparencia_base_url: str = "https://api.portaldatransparencia.gov.br"
    portal_transparencia_api_key: str = ""
    lista_suja_pdf_url: str = (
        "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/inspecao-do-trabalho/"
        "areas-de-atuacao/cadastro_de_empregadores.pdf"
    )
    restrictive_list_max_pages: int = 10000
    # Paces requests to the CGU API during ingestion — a full historical load is
    # thousands of pages, and firing them with no delay risks tripping their own
    # rate limiting or getting our IP flagged, breaking this feature entirely.
    restrictive_list_page_delay_seconds: float = 0.2

    # Dev-only default — every deployment must override this via env.
    secret_key: str = DEV_SECRET_KEY
    access_token_expire_minutes: int = 10080  # 7 days

    reprocess_interval_hours: int = 24
    restrictive_list_ingest_interval_hours: int = 24
    worker_poll_interval_seconds: int = 60
    stale_job_minutes: int = 30

    # Empty by default (endpoint fails closed): set this to enable
    # POST /api/v1/internal/worker/run-once, which lets an external
    # scheduler (e.g. a GitHub Actions cron job) trigger one worker pass
    # without needing a paid always-on background worker service.
    worker_trigger_secret: str = ""


# RFC 7518 §3.2's minimum for an HS256 key — PyJWT itself warns below this.
_MIN_SECRET_KEY_LENGTH = 32


def assert_production_ready(settings: Settings) -> None:
    """Refuses to boot with a placeholder or weak JWT secret in production.

    A leaked/guessable/too-short SECRET_KEY lets anyone forge a valid auth
    token for any user — this is exactly the kind of misconfiguration that's
    invisible until it's exploited, so it fails loudly at startup instead.
    Checking length, not just "isn't the literal placeholder", matters: a
    short replacement like SECRET_KEY=mypassword123 would pass the first
    check while still being a weak HS256 key (PyJWT warns under 32 bytes).
    """
    if settings.environment != "production":
        return

    if settings.secret_key == DEV_SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY is still the development default. Set a real secret "
            "(e.g. `openssl rand -hex 32`) before running with ENVIRONMENT=production."
        )
    if len(settings.secret_key) < _MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY is only {len(settings.secret_key)} characters — too short "
            f"for secure JWT signing (need at least {_MIN_SECRET_KEY_LENGTH}). "
            "Generate a proper one: openssl rand -hex 32"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
