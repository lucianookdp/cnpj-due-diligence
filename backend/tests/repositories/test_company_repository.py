from datetime import UTC, date, datetime

from app.models import Person
from app.providers.base import RawCompanyData, RawPartner
from app.repositories import company_repository


def _raw(cnpj="11222333000181", partners=None, **overrides) -> RawCompanyData:
    defaults = {
        "cnpj": cnpj,
        "razao_social": "EMPRESA TESTE LTDA",
        "nome_fantasia": "TESTE",
        "situacao_cadastral": "ATIVA",
        "situacao_cadastral_data": None,
        "data_abertura": None,
        "capital_social": None,
        "natureza_juridica_codigo": "206-2",
        "natureza_juridica_descricao": "Sociedade Empresária Limitada",
        "porte": "ME",
        "cnae_principal_codigo": "6201500",
        "cnae_principal_descricao": "Desenvolvimento de programas de computador",
        "cnaes_secundarios": [],
        "logradouro": "RUA TESTE",
        "numero": "100",
        "complemento": None,
        "bairro": "CENTRO",
        "municipio": "SAO PAULO",
        "uf": "SP",
        "cep": "01310100",
        "partners": partners or [],
        "source_provider": "minha_receita",
        "raw_response": {"cnpj": cnpj},
    }
    defaults.update(overrides)
    return RawCompanyData(**defaults)


def test_upsert_creates_new_company(db):
    raw = _raw()

    company = company_repository.upsert_from_provider(db, raw)

    assert company.id is not None
    assert company.cnpj == "11222333000181"
    assert company.razao_social == "EMPRESA TESTE LTDA"
    assert company.address_key == "01310100:100"


def test_upsert_updates_existing_company_by_cnpj(db):
    company_repository.upsert_from_provider(db, _raw(razao_social="NOME ANTIGO"))
    db.flush()

    updated = company_repository.upsert_from_provider(db, _raw(razao_social="NOME NOVO"))

    assert updated.razao_social == "NOME NOVO"
    assert db.query(type(updated)).count() == 1


def test_upsert_creates_partnerships_for_partners(db):
    partner = RawPartner(
        nome="FULANO DE TAL",
        documento="***123456**",
        tipo_socio="pessoa_fisica",
        faixa_etaria="31 a 40 anos",
        qualificacao="Sócio",
        entrada_sociedade=None,
    )

    company = company_repository.upsert_from_provider(db, _raw(partners=[partner]))
    db.flush()

    active = [p for p in company.partnerships if p.ended_at is None]
    assert len(active) == 1
    assert active[0].person.nome == "FULANO DE TAL"
    assert active[0].qualificacao == "Sócio"


def test_new_partnership_uses_real_entrada_sociedade_date_not_now(db):
    partner = RawPartner(
        nome="FULANO DE TAL",
        documento="***123456**",
        tipo_socio="pessoa_fisica",
        faixa_etaria="31 a 40 anos",
        qualificacao="Sócio",
        entrada_sociedade=date(2019, 3, 10),
    )

    company = company_repository.upsert_from_provider(db, _raw(partners=[partner]))
    db.flush()

    partnership = company.partnerships[0]
    assert partnership.first_seen_at.date() == date(2019, 3, 10)


def test_new_partnership_falls_back_to_now_when_no_entrada_sociedade(db):
    partner = RawPartner(
        nome="FULANO DE TAL",
        documento="***123456**",
        tipo_socio="pessoa_fisica",
        faixa_etaria="31 a 40 anos",
        qualificacao="Sócio",
        entrada_sociedade=None,
    )

    company = company_repository.upsert_from_provider(db, _raw(partners=[partner]))
    db.flush()

    partnership = company.partnerships[0]
    assert partnership.first_seen_at.date() == datetime.now(UTC).date()


def test_partner_removed_from_qsa_gets_ended_instead_of_deleted(db):
    partner = RawPartner(
        nome="FULANO DE TAL",
        documento="***123456**",
        tipo_socio="pessoa_fisica",
        faixa_etaria="31 a 40 anos",
        qualificacao="Sócio",
        entrada_sociedade=None,
    )
    company = company_repository.upsert_from_provider(db, _raw(partners=[partner]))
    db.flush()

    company = company_repository.upsert_from_provider(db, _raw(partners=[]))
    db.flush()

    assert len(company.partnerships) == 1
    assert company.partnerships[0].ended_at is not None


def test_pessoa_juridica_partner_is_not_persisted_as_a_person(db):
    pj_partner = RawPartner(
        nome="HOLDING EXEMPLO LTDA",
        documento="11222333000199",
        tipo_socio="pessoa_juridica",
        faixa_etaria=None,
        qualificacao="Sócio",
        entrada_sociedade=None,
    )

    company = company_repository.upsert_from_provider(db, _raw(partners=[pj_partner]))
    db.flush()

    assert company.partnerships == []
    assert db.query(Person).filter(Person.nome == "HOLDING EXEMPLO LTDA").one_or_none() is None


def test_reused_person_shares_row_across_companies(db):
    partner = RawPartner(
        nome="FULANO DE TAL",
        documento="***123456**",
        tipo_socio="pessoa_fisica",
        faixa_etaria="31 a 40 anos",
        qualificacao="Sócio",
        entrada_sociedade=None,
    )
    company_a = company_repository.upsert_from_provider(
        db, _raw(cnpj="11222333000181", partners=[partner])
    )
    db.flush()
    company_b = company_repository.upsert_from_provider(
        db, _raw(cnpj="99888777000199", partners=[partner])
    )
    db.flush()

    person_a = company_a.partnerships[0].person_id
    person_b = company_b.partnerships[0].person_id
    assert person_a == person_b
