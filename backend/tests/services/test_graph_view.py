from datetime import UTC, datetime

from app.models import Company, Partnership, Person
from app.services import graph_view


def _make_company(db, cnpj, address_key=None) -> Company:
    company = Company(
        cnpj=cnpj,
        razao_social="EMPRESA " + cnpj,
        situacao_cadastral="ATIVA",
        source_provider="minha_receita",
        source_collected_at=datetime.now(UTC),
        raw_response={},
        address_key=address_key,
    )
    db.add(company)
    db.flush()
    return company


def test_flags_person_linked_to_two_or_more_companies_as_shared_partner(db):
    company_a = _make_company(db, "11111111000101")
    company_b = _make_company(db, "22222222000102")
    person = Person(nome="FULANO", cpf_masked="***123456**")
    db.add(person)
    db.flush()
    db.add(Partnership(person_id=person.id, company_id=company_a.id))
    db.add(Partnership(person_id=person.id, company_id=company_b.id))
    db.flush()

    _, _, indicators = graph_view.render_subgraph(
        db, {company_a.id, company_b.id, person.id}, shared_address_threshold=5
    )

    assert indicators.shared_partner_person_ids == [person.id]


def test_flags_address_shared_above_threshold(db):
    key = "70040912:SN"
    companies = [_make_company(db, f"1111111100010{i}", address_key=key) for i in range(3)]
    db.flush()

    _, _, indicators = graph_view.render_subgraph(
        db, {c.id for c in companies}, shared_address_threshold=2
    )

    assert indicators.shared_address_keys == {key: 3}


def test_does_not_flag_address_at_or_below_threshold(db):
    key = "70040912:SN"
    companies = [_make_company(db, f"1111111100010{i}", address_key=key) for i in range(2)]
    db.flush()

    _, _, indicators = graph_view.render_subgraph(
        db, {c.id for c in companies}, shared_address_threshold=2
    )

    assert indicators.shared_address_keys == {}
