import httpx

from app.providers.base import CompanyNotFoundError, ProviderError, RawCompanyData
from app.providers.receita_schema import parse_receita_payload


class MinhaReceitaProvider:
    name = "minha_receita"

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_company(self, cnpj: str) -> RawCompanyData:
        url = f"{self._base_url}/{cnpj}"
        try:
            response = httpx.get(url, timeout=self._timeout_seconds)
        except httpx.HTTPError as exc:
            raise ProviderError(f"minha_receita request failed: {exc}") from exc

        if response.status_code == 404:
            raise CompanyNotFoundError(cnpj)
        if response.status_code != 200:
            raise ProviderError(f"minha_receita returned status {response.status_code}")

        return parse_receita_payload(response.json(), source_provider=self.name)
