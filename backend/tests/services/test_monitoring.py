from datetime import UTC, datetime

from app.models import Company, Partnership, Person
from app.repositories import restrictive_list_repository
from app.repositories.restrictive_list_repository import RawRestrictiveListEntry
from app.services import monitoring


def _company(db, cnpj="11222333000181", situacao="ATIVA") -> Company:
    company = Company(
        cnpj=cnpj,
        razao_social="EMPRESA TESTE",
        situacao_cadastral=situacao,
        source_provider="minha_receita",
        source_collected_at=datetime.now(UTC),
        raw_response={},
    )
    db.add(company)
    db.flush()
    return company


def test_snapshot_captures_situacao_and_active_partners(db):
    company = _company(db)
    person = Person(nome="FULANO", cpf_masked="***123456**")
    db.add(person)
    db.flush()
    db.add(Partnership(person_id=person.id, company_id=company.id))
    db.flush()

    snap = monitoring.snapshot(db, company)

    assert snap.situacao_cadastral == "ATIVA"
    assert ("***123456**", "FULANO") in snap.active_partner_keys


def test_snapshot_excludes_ended_partnerships(db):
    company = _company(db)
    person = Person(nome="FULANO", cpf_masked="***123456**")
    db.add(person)
    db.flush()
    db.add(Partnership(person_id=person.id, company_id=company.id, ended_at=datetime.now(UTC)))
    db.flush()

    snap = monitoring.snapshot(db, company)

    assert snap.active_partner_keys == frozenset()


def test_snapshot_captures_restrictive_matches(db):
    company = _company(db)
    restrictive_list_repository.upsert_entry(
        db,
        RawRestrictiveListEntry(
            list_type="ceis",
            external_id="1",
            document=company.cnpj,
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

    snap = monitoring.snapshot(db, company)

    assert ("ceis", "1") in snap.restrictive_match_keys


def test_detect_changes_flags_situacao_change():
    before = monitoring.CompanySnapshot("ATIVA", frozenset(), frozenset())
    after = monitoring.CompanySnapshot("BAIXADA", frozenset(), frozenset())

    changes = monitoring.detect_changes(before, after)

    assert ("situacao_alterada", "Situação cadastral mudou de 'ATIVA' para 'BAIXADA'") in changes


def test_detect_changes_no_situacao_change():
    before = monitoring.CompanySnapshot("ATIVA", frozenset(), frozenset())
    after = monitoring.CompanySnapshot("ATIVA", frozenset(), frozenset())

    changes = monitoring.detect_changes(before, after)

    assert not any(c[0] == "situacao_alterada" for c in changes)


def test_detect_changes_flags_new_restrictive_match():
    before = monitoring.CompanySnapshot("ATIVA", frozenset(), frozenset())
    after = monitoring.CompanySnapshot("ATIVA", frozenset(), frozenset({("ceis", "1")}))

    changes = monitoring.detect_changes(before, after)

    assert any(c[0] == "nova_lista_restritiva" for c in changes)


def test_detect_changes_no_alert_for_preexisting_match():
    before = monitoring.CompanySnapshot("ATIVA", frozenset(), frozenset({("ceis", "1")}))
    after = monitoring.CompanySnapshot("ATIVA", frozenset(), frozenset({("ceis", "1")}))

    changes = monitoring.detect_changes(before, after)

    assert not any(c[0] == "nova_lista_restritiva" for c in changes)


def test_detect_changes_flags_partner_added_and_removed():
    before = monitoring.CompanySnapshot("ATIVA", frozenset({("***111**", "A")}), frozenset())
    after = monitoring.CompanySnapshot("ATIVA", frozenset({("***222**", "B")}), frozenset())

    changes = monitoring.detect_changes(before, after)

    socio_changes = [c for c in changes if c[0] == "socio_alterado"]
    assert len(socio_changes) == 1
    assert "incluído" in socio_changes[0][1]
    assert "removido" in socio_changes[0][1]


def test_detect_changes_returns_empty_for_identical_snapshots():
    snap = monitoring.CompanySnapshot("ATIVA", frozenset({("***111**", "A")}), frozenset())

    assert monitoring.detect_changes(snap, snap) == []
