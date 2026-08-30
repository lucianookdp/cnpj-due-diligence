from datetime import UTC, datetime

from app.models import Company, Partnership, Person
from app.repositories import restrictive_list_repository
from app.repositories.restrictive_list_repository import RawRestrictiveListEntry
from app.services import risk_scoring


def _company(db, cnpj="11222333000181", address_key=None) -> Company:
    company = Company(
        cnpj=cnpj,
        razao_social="EMPRESA TESTE",
        situacao_cadastral="ATIVA",
        source_provider="minha_receita",
        source_collected_at=datetime.now(UTC),
        raw_response={},
        address_key=address_key,
    )
    db.add(company)
    db.flush()
    return company


def test_build_context_counts_shared_address(db):
    key = "70040912:SN"
    _company(db, cnpj="11222333000181", address_key=key)
    _company(db, cnpj="22222222000122", address_key=key)
    target = _company(db, cnpj="33333333000133", address_key=key)
    db.flush()

    ctx = risk_scoring.build_context(db, target, None)

    assert ctx.shared_address_company_count == 3


def test_build_context_finds_restrictive_match_by_company_cnpj(db):
    company = _company(db, cnpj="11222333000181")
    restrictive_list_repository.upsert_entry(
        db,
        RawRestrictiveListEntry(
            list_type="ceis",
            external_id="1",
            document="11222333000181",
            document_type="cnpj",
            name="EMPRESA TESTE",
            reason=None,
            source_org=None,
            sanction_start_date=None,
            sanction_end_date=None,
            raw_data={},
        ),
    )
    db.flush()

    ctx = risk_scoring.build_context(db, company, None)

    assert len(ctx.restrictive_matches) == 1


def test_build_context_finds_restrictive_match_by_active_partner_cpf(db):
    company = _company(db)
    person = Person(nome="FULANO", cpf_masked="***123456**")
    db.add(person)
    db.flush()
    db.add(Partnership(person_id=person.id, company_id=company.id))
    restrictive_list_repository.upsert_entry(
        db,
        RawRestrictiveListEntry(
            list_type="cnep",
            external_id="1",
            document="12312345678",
            document_type="cpf",
            name="FULANO",
            reason=None,
            source_org=None,
            sanction_start_date=None,
            sanction_end_date=None,
            raw_data={},
        ),
    )
    db.flush()

    ctx = risk_scoring.build_context(db, company, None)

    assert len(ctx.restrictive_matches) == 1


def test_build_context_ignores_ended_partnerships_for_matching(db):
    company = _company(db)
    person = Person(nome="FULANO", cpf_masked="***123456**")
    db.add(person)
    db.flush()
    db.add(Partnership(person_id=person.id, company_id=company.id, ended_at=datetime.now(UTC)))
    restrictive_list_repository.upsert_entry(
        db,
        RawRestrictiveListEntry(
            list_type="cnep",
            external_id="1",
            document="12312345678",
            document_type="cpf",
            name="FULANO",
            reason=None,
            source_org=None,
            sanction_start_date=None,
            sanction_end_date=None,
            raw_data={},
        ),
    )
    db.flush()

    ctx = risk_scoring.build_context(db, company, None)

    assert ctx.restrictive_matches == []
