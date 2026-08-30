from datetime import UTC, datetime

from app.models import Company, CompanyPartnership, Partnership, Person
from app.repositories import graph_repository


def _make_company(db, cnpj, razao_social="EMPRESA", address_key=None) -> Company:
    company = Company(
        cnpj=cnpj,
        razao_social=razao_social,
        situacao_cadastral="ATIVA",
        source_provider="minha_receita",
        source_collected_at=datetime.now(UTC),
        raw_response={},
        address_key=address_key,
    )
    db.add(company)
    db.flush()
    return company


def _make_person(db, nome, cpf_masked="***123456**") -> Person:
    person = Person(nome=nome, cpf_masked=cpf_masked)
    db.add(person)
    db.flush()
    return person


def test_get_reachable_node_ids_respects_depth(db):
    company_a = _make_company(db, "11111111000101")
    company_b = _make_company(db, "22222222000102")
    person = _make_person(db, "FULANO")
    db.add(Partnership(person_id=person.id, company_id=company_a.id))
    db.add(Partnership(person_id=person.id, company_id=company_b.id))
    db.flush()

    depth_zero = graph_repository.get_reachable_node_ids(
        db, company_a.id, max_depth=0, max_nodes=100
    )
    depth_one = graph_repository.get_reachable_node_ids(
        db, company_a.id, max_depth=1, max_nodes=100
    )
    depth_two = graph_repository.get_reachable_node_ids(
        db, company_a.id, max_depth=2, max_nodes=100
    )

    assert depth_zero == {company_a.id}
    assert depth_one == {company_a.id, person.id}
    assert depth_two == {company_a.id, person.id, company_b.id}


def test_get_reachable_node_ids_follows_company_partnerships(db):
    subject = _make_company(db, "11111111000101")
    object_company = _make_company(db, "22222222000102")
    db.add(CompanyPartnership(subject_company_id=subject.id, object_company_id=object_company.id))
    db.flush()

    reachable = graph_repository.get_reachable_node_ids(
        db, object_company.id, max_depth=1, max_nodes=100
    )

    assert reachable == {object_company.id, subject.id}


def test_get_reachable_node_ids_ignores_ended_edges(db):
    company_a = _make_company(db, "11111111000101")
    company_b = _make_company(db, "22222222000102")
    person = _make_person(db, "FULANO")
    db.add(Partnership(person_id=person.id, company_id=company_a.id))
    db.add(Partnership(person_id=person.id, company_id=company_b.id, ended_at=datetime.now(UTC)))
    db.flush()

    reachable = graph_repository.get_reachable_node_ids(
        db, company_a.id, max_depth=2, max_nodes=100
    )

    assert company_b.id not in reachable


def test_get_subgraph_excludes_edges_with_endpoint_outside_set(db):
    company_a = _make_company(db, "11111111000101")
    company_b = _make_company(db, "22222222000102")
    person = _make_person(db, "FULANO")
    db.add(Partnership(person_id=person.id, company_id=company_a.id))
    db.add(Partnership(person_id=person.id, company_id=company_b.id))
    db.flush()

    companies, people, partnerships, company_partnerships = graph_repository.get_subgraph(
        db, {company_a.id, person.id}
    )

    assert {c.id for c in companies} == {company_a.id}
    assert {p.id for p in people} == {person.id}
    assert len(partnerships) == 1
    assert partnerships[0].company_id == company_a.id
    assert company_partnerships == []


def test_count_companies_by_address_key(db):
    _make_company(db, "11111111000101", address_key="70040912:SN")
    _make_company(db, "22222222000102", address_key="70040912:SN")
    _make_company(db, "33333333000103", address_key="99999999:1")
    db.flush()

    counts = graph_repository.count_companies_by_address_key(db, {"70040912:SN", "99999999:1"})

    assert counts["70040912:SN"] == 2
    assert counts["99999999:1"] == 1
