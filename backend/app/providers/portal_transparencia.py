import httpx

from app.providers.base import ProviderError

_ENDPOINTS = {
    "ceis": "/api-de-dados/ceis",
    "cnep": "/api-de-dados/cnep",
    "cepim": "/api-de-dados/cepim",
    "leniencia": "/api-de-dados/acordos-leniencia",
}


class PortalTransparenciaProvider:
    """Official CGU API for CEIS/CNEP/CEPIM/Acordos de Leniência.

    Requires a free API key from a one-time email registration at
    portaldatransparencia.gov.br/api-de-dados/cadastrar-email — there is no
    anonymous access (the OpenAPI spec claims otherwise, but the API itself
    returns 401 without the chave-api-dados header).
    """

    name = "portal_transparencia"

    def __init__(self, base_url: str, api_key: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def fetch_page(self, list_type: str, pagina: int) -> list[dict]:
        path = _ENDPOINTS[list_type]
        try:
            response = httpx.get(
                f"{self._base_url}{path}",
                params={"pagina": pagina},
                headers={"chave-api-dados": self._api_key},
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"portal_transparencia request failed: {exc}") from exc

        if response.status_code == 401:
            raise ProviderError(
                "portal_transparencia rejected the API key — check "
                "PORTAL_TRANSPARENCIA_API_KEY (chave-api-dados header)"
            )
        if response.status_code != 200:
            raise ProviderError(f"portal_transparencia returned status {response.status_code}")

        return response.json()
