import pytest

from app.providers.base import CompanyNotFoundError, ProviderError, RawCompanyData
from app.providers.resolver import ProviderResolver


class _StubProvider:
    def __init__(self, name: str, outcome):
        self.name = name
        self._outcome = outcome

    def fetch_company(self, cnpj: str) -> RawCompanyData:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def _stub_data(source: str) -> RawCompanyData:
    return RawCompanyData(
        cnpj="00000000000191",
        razao_social="STUB",
        nome_fantasia=None,
        situacao_cadastral="ATIVA",
        situacao_cadastral_data=None,
        data_abertura=None,
        capital_social=None,
        natureza_juridica_codigo=None,
        natureza_juridica_descricao=None,
        porte=None,
        cnae_principal_codigo=None,
        cnae_principal_descricao=None,
        cnaes_secundarios=[],
        logradouro=None,
        numero=None,
        complemento=None,
        bairro=None,
        municipio=None,
        uf=None,
        cep=None,
        partners=[],
        source_provider=source,
        raw_response={},
    )


def test_uses_primary_provider_when_it_succeeds():
    primary = _StubProvider("primary", _stub_data("primary"))
    fallback = _StubProvider("fallback", _stub_data("fallback"))
    resolver = ProviderResolver([primary, fallback])

    data = resolver.fetch_company("00000000000191")

    assert data.source_provider == "primary"


def test_falls_back_when_primary_raises_provider_error():
    primary = _StubProvider("primary", ProviderError("boom"))
    fallback = _StubProvider("fallback", _stub_data("fallback"))
    resolver = ProviderResolver([primary, fallback])

    data = resolver.fetch_company("00000000000191")

    assert data.source_provider == "fallback"


def test_does_not_fall_back_on_not_found():
    primary = _StubProvider("primary", CompanyNotFoundError("00000000000191"))
    fallback = _StubProvider("fallback", _stub_data("fallback"))
    resolver = ProviderResolver([primary, fallback])

    with pytest.raises(CompanyNotFoundError):
        resolver.fetch_company("00000000000191")


def test_raises_last_error_when_all_providers_fail():
    primary = _StubProvider("primary", ProviderError("first failure"))
    fallback = _StubProvider("fallback", ProviderError("second failure"))
    resolver = ProviderResolver([primary, fallback])

    with pytest.raises(ProviderError, match="second failure"):
        resolver.fetch_company("00000000000191")
