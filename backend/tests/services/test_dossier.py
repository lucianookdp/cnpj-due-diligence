from datetime import UTC, datetime, timedelta

import pytest

from app.providers.base import CompanyNotFoundError, RawCompanyData
from app.repositories import company_repository
from app.services.dossier import DossierNotFoundError, get_dossier


class _StubResolver:
    def __init__(self, outcome):
        self._outcome = outcome
        self.calls = 0

    def fetch_company(self, cnpj: str) -> RawCompanyData:
        self.calls += 1
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def _raw(cnpj="11222333000181") -> RawCompanyData:
    return RawCompanyData(
        cnpj=cnpj,
        razao_social="EMPRESA TESTE LTDA",
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
        source_provider="minha_receita",
        raw_response={},
    )


def test_fetches_from_provider_when_no_cached_row(db):
    resolver = _StubResolver(_raw())

    dossier = get_dossier(db, resolver, "11222333000181", cache_ttl_hours=720)

    assert dossier.cnpj == "11222333000181"
    assert resolver.calls == 1


def test_serves_from_cache_within_ttl(db):
    resolver = _StubResolver(_raw())
    get_dossier(db, resolver, "11222333000181", cache_ttl_hours=720)

    get_dossier(db, resolver, "11222333000181", cache_ttl_hours=720)

    assert resolver.calls == 1


def test_refetches_when_cached_row_is_stale(db):
    resolver = _StubResolver(_raw())
    get_dossier(db, resolver, "11222333000181", cache_ttl_hours=720)
    company = company_repository.get_by_cnpj(db, "11222333000181")
    company.source_collected_at = datetime.now(UTC) - timedelta(hours=800)
    db.flush()
    db.commit()

    get_dossier(db, resolver, "11222333000181", cache_ttl_hours=720)

    assert resolver.calls == 2


def test_raises_dossier_not_found_when_provider_reports_not_found(db):
    resolver = _StubResolver(CompanyNotFoundError("00000000000000"))

    with pytest.raises(DossierNotFoundError):
        get_dossier(db, resolver, "00000000000000", cache_ttl_hours=720)


def test_recovers_when_a_concurrent_request_inserts_the_same_cnpj_first(db, monkeypatch):
    """Graph discovery can reach the same CNPJ from two overlapping requests
    (e.g. the root dossier and root graph fetch racing each other, or two
    branches of a BFS expansion in separate requests). Both see a cache miss
    before either commits, so the second one to flush its insert hits
    companies' unique cnpj constraint instead of a clean cache hit. This
    reproduces that by forcing every get_by_cnpj lookup to report "not found"
    until after the real insert has already failed, then lets the real
    lookup through for the recovery path.
    """
    resolver = _StubResolver(_raw())
    get_dossier(db, resolver, "11222333000181", cache_ttl_hours=720)  # pre-existing committed row

    original_get_by_cnpj = company_repository.get_by_cnpj
    call_count = {"n": 0}

    def fake_get_by_cnpj(db_, cnpj):
        call_count["n"] += 1
        # Calls 1 and 2 are ensure_company's own cache check and
        # upsert_from_provider's internal one, both racing ahead of the
        # other transaction's commit; call 3+ is the post-rollback recovery
        # fetch, which must see the real, already-committed row.
        if call_count["n"] <= 2:
            return None
        return original_get_by_cnpj(db_, cnpj)

    monkeypatch.setattr(company_repository, "get_by_cnpj", fake_get_by_cnpj)

    dossier = get_dossier(db, resolver, "11222333000181", cache_ttl_hours=720)

    assert dossier.cnpj == "11222333000181"
