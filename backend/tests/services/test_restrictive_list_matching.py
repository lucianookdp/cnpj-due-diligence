from app.repositories import restrictive_list_repository
from app.repositories.restrictive_list_repository import RawRestrictiveListEntry
from app.services import restrictive_list_matching


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


def test_match_by_cnpj_finds_exact_document(db):
    restrictive_list_repository.upsert_entry(db, _entry())
    db.flush()

    matches = restrictive_list_matching.match_by_cnpj(db, "11222333000181")

    assert len(matches) == 1


def test_match_by_cnpj_no_match(db):
    restrictive_list_repository.upsert_entry(db, _entry())
    db.flush()

    assert restrictive_list_matching.match_by_cnpj(db, "00000000000000") == []


def test_match_by_masked_cpf_finds_full_cpf_via_mask(db):
    restrictive_list_repository.upsert_entry(
        db,
        _entry(
            external_id="2",
            document="07680247730",
            document_type="cpf",
            name="FULANO",
        ),
    )
    db.flush()

    matches = restrictive_list_matching.match_by_masked_cpf(db, "***802477**")

    assert len(matches) == 1
    assert matches[0].name == "FULANO"


def test_match_by_masked_cpf_returns_empty_for_none(db):
    assert restrictive_list_matching.match_by_masked_cpf(db, None) == []
