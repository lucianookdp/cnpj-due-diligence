import httpx
import pytest
import respx

from app.providers.base import ProviderError
from app.providers.grafo_minha_receita import GrafoMinhaReceitaProvider


@respx.mock
def test_fetch_relations_by_cnpj_returns_partners():
    respx.get("https://grafo.minhareceita.org/00000000000191").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "cnpj": "00000000000191",
                    "razao_social": "BANCO DO BRASIL SA",
                    "id": "abc123",
                    "nome": "FULANO DE TAL",
                    "cpf": "***550179**",
                }
            ],
        )
    )
    provider = GrafoMinhaReceitaProvider("https://grafo.minhareceita.org", timeout_seconds=5)

    relations = provider.fetch_relations("00000000000191")

    assert len(relations) == 1
    assert relations[0].graph_ref_id == "abc123"
    assert relations[0].nome == "FULANO DE TAL"
    assert relations[0].cpf_masked == "***550179**"


@respx.mock
def test_fetch_relations_by_person_ref_returns_companies():
    respx.get("https://grafo.minhareceita.org/abc123").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "cnpj": "11111111000111",
                    "razao_social": "EMPRESA A",
                    "id": "abc123",
                    "nome": "X",
                    "cpf": None,
                },
                {
                    "cnpj": "22222222000122",
                    "razao_social": "EMPRESA B",
                    "id": "abc123",
                    "nome": "X",
                    "cpf": None,
                },
            ],
        )
    )
    provider = GrafoMinhaReceitaProvider("https://grafo.minhareceita.org", timeout_seconds=5)

    relations = provider.fetch_relations("abc123")

    assert {r.cnpj for r in relations} == {"11111111000111", "22222222000122"}


@respx.mock
def test_raises_provider_error_on_failure_status():
    respx.get("https://grafo.minhareceita.org/00000000000000").mock(
        return_value=httpx.Response(500)
    )
    provider = GrafoMinhaReceitaProvider("https://grafo.minhareceita.org", timeout_seconds=5)

    with pytest.raises(ProviderError):
        provider.fetch_relations("00000000000000")


@respx.mock
def test_raises_provider_error_on_unexpected_shape():
    respx.get("https://grafo.minhareceita.org/xyz").mock(
        return_value=httpx.Response(200, json={"message": "oops"})
    )
    provider = GrafoMinhaReceitaProvider("https://grafo.minhareceita.org", timeout_seconds=5)

    with pytest.raises(ProviderError):
        provider.fetch_relations("xyz")
