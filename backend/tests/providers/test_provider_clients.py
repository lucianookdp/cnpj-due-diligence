import json
from pathlib import Path

import httpx
import pytest
import respx

from app.providers.base import CompanyNotFoundError, ProviderError
from app.providers.brasil_api import BrasilApiProvider
from app.providers.minha_receita import MinhaReceitaProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"
PAYLOAD = json.loads((FIXTURES / "banco_do_brasil.json").read_text())


@respx.mock
def test_minha_receita_fetches_and_normalizes():
    respx.get("https://minhareceita.org/00000000000191").mock(
        return_value=httpx.Response(200, json=PAYLOAD)
    )
    provider = MinhaReceitaProvider("https://minhareceita.org", timeout_seconds=5)

    data = provider.fetch_company("00000000000191")

    assert data.cnpj == "00000000000191"
    assert data.source_provider == "minha_receita"


@respx.mock
def test_minha_receita_raises_not_found_on_404():
    respx.get("https://minhareceita.org/00000000000000").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )
    provider = MinhaReceitaProvider("https://minhareceita.org", timeout_seconds=5)

    with pytest.raises(CompanyNotFoundError):
        provider.fetch_company("00000000000000")


@respx.mock
def test_minha_receita_raises_provider_error_on_server_error():
    respx.get("https://minhareceita.org/00000000000191").mock(return_value=httpx.Response(500))
    provider = MinhaReceitaProvider("https://minhareceita.org", timeout_seconds=5)

    with pytest.raises(ProviderError):
        provider.fetch_company("00000000000191")


@respx.mock
def test_brasil_api_fetches_and_normalizes():
    respx.get("https://brasilapi.com.br/api/cnpj/v1/00000000000191").mock(
        return_value=httpx.Response(200, json=PAYLOAD)
    )
    provider = BrasilApiProvider("https://brasilapi.com.br/api", timeout_seconds=5)

    data = provider.fetch_company("00000000000191")

    assert data.cnpj == "00000000000191"
    assert data.source_provider == "brasil_api"
