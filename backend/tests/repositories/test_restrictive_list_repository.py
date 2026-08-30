from app.repositories import restrictive_list_repository
from app.repositories.restrictive_list_repository import RawRestrictiveListEntry


def _entry(**overrides) -> RawRestrictiveListEntry:
    defaults = {
        "list_type": "ceis",
        "external_id": "1",
        "document": "11222333000181",
        "document_type": "cnpj",
        "name": "EMPRESA EXEMPLO LTDA",
        "reason": "Suspensão",
        "source_org": "TCU",
        "sanction_start_date": None,
        "sanction_end_date": None,
        "raw_data": {},
    }
    defaults.update(overrides)
    return RawRestrictiveListEntry(**defaults)


def test_upsert_creates_new_entry(db):
    row = restrictive_list_repository.upsert_entry(db, _entry())

    assert row.id is not None
    assert row.document == "11222333000181"


def test_upsert_updates_existing_entry_by_list_type_and_external_id(db):
    restrictive_list_repository.upsert_entry(db, _entry(name="NOME ANTIGO"))
    db.flush()

    updated = restrictive_list_repository.upsert_entry(db, _entry(name="NOME NOVO"))

    assert updated.name == "NOME NOVO"
    assert db.query(type(updated)).count() == 1


def test_different_list_types_with_same_external_id_stay_distinct(db):
    restrictive_list_repository.upsert_entry(db, _entry(list_type="ceis", external_id="1"))
    restrictive_list_repository.upsert_entry(db, _entry(list_type="cnep", external_id="1"))
    db.flush()

    row = restrictive_list_repository.upsert_entry(db, _entry(list_type="ceis", external_id="1"))
    assert db.query(type(row)).count() == 2


def test_find_by_document(db):
    restrictive_list_repository.upsert_entry(db, _entry(document="11222333000181"))
    restrictive_list_repository.upsert_entry(db, _entry(external_id="2", document="99999999000199"))
    db.flush()

    results = restrictive_list_repository.find_by_document(db, "11222333000181")

    assert len(results) == 1
    assert results[0].document == "11222333000181"
