import logging

from app.core.config import Settings
from app.providers.base import (
    CompanyDataProvider,
    CompanyNotFoundError,
    ProviderError,
    RawCompanyData,
)
from app.providers.brasil_api import BrasilApiProvider
from app.providers.minha_receita import MinhaReceitaProvider

logger = logging.getLogger(__name__)


class ProviderResolver:
    """Tries providers in order, falling back on ProviderError.

    CompanyNotFoundError is not retried across providers: an authoritative
    "does not exist" from one government-backed source is treated as final.
    """

    def __init__(self, providers: list[CompanyDataProvider]) -> None:
        if not providers:
            raise ValueError("ProviderResolver requires at least one provider")
        self._providers = providers

    def fetch_company(self, cnpj: str) -> RawCompanyData:
        last_error: ProviderError | None = None
        for provider in self._providers:
            try:
                return provider.fetch_company(cnpj)
            except CompanyNotFoundError:
                raise
            except ProviderError as exc:
                logger.warning("provider %s failed for cnpj %s: %s", provider.name, cnpj, exc)
                last_error = exc
        raise last_error or ProviderError("no providers configured")


def build_default_resolver(settings: Settings) -> ProviderResolver:
    return ProviderResolver(
        [
            MinhaReceitaProvider(
                settings.minha_receita_base_url, settings.provider_timeout_seconds
            ),
            BrasilApiProvider(settings.brasil_api_base_url, settings.provider_timeout_seconds),
        ]
    )
