from app.providers.base import CompanyNotFoundError, RawCompanyData
from app.repositories import company_repository
from app.services import reprocessing


def _raw(cnpj="11222333000181", situacao="ATIVA") -> RawCompanyData:
    return RawCompanyData(
        cnpj=cnpj,
        razao_social="EMPRESA TESTE",
        nome_fantasia=None,
        situacao_cadastral=situacao,
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


class _StubResolver:
    def __init__(self, data: RawCompanyData):
        self._data = data

    def fetch_company(self, cnpj: str) -> RawCompanyData:
        if cnpj != self._data.cnpj:
            raise CompanyNotFoundError(cnpj)
        return self._data


def test_first_reprocess_produces_no_alerts(db):
    resolver = _StubResolver(_raw())

    alerts = reprocessing.reprocess_company(db, resolver, "11222333000181")

    assert alerts == []
    assert company_repository.get_by_cnpj(db, "11222333000181") is not None


def test_second_reprocess_detects_situacao_change(db):
    company_repository.upsert_from_provider(db, _raw(situacao="ATIVA"))
    db.commit()
    resolver = _StubResolver(_raw(situacao="BAIXADA"))

    alerts = reprocessing.reprocess_company(db, resolver, "11222333000181")

    assert len(alerts) == 1
    assert alerts[0].alert_type == "situacao_alterada"


def test_reprocess_with_no_changes_produces_no_alerts(db):
    company_repository.upsert_from_provider(db, _raw())
    db.commit()
    resolver = _StubResolver(_raw())

    alerts = reprocessing.reprocess_company(db, resolver, "11222333000181")

    assert alerts == []
