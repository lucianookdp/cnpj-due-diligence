from app.models import RestrictiveListEntry
from app.providers.base import ProviderError
from app.services import restrictive_list_ingestion


def _ceis_record(record_id: int, cnpj: str) -> dict:
    return {
        "id": record_id,
        "dataInicioSancao": None,
        "dataFimSancao": None,
        "tipoSancao": {"descricaoResumida": "Suspensão"},
        "orgaoSancionador": {"nome": "TCU"},
        "sancionado": {"nome": "EMPRESA", "codigoFormatado": cnpj},
    }


class _StubPortal:
    def __init__(self, pages_by_list: dict[str, list[list[dict]]], fail_list: str | None = None):
        self._pages_by_list = pages_by_list
        self._fail_list = fail_list
        self.calls: list[tuple[str, int]] = []

    def fetch_page(self, list_type: str, pagina: int) -> list[dict]:
        self.calls.append((list_type, pagina))
        if list_type == self._fail_list:
            raise ProviderError("boom")
        pages = self._pages_by_list.get(list_type, [])
        if pagina > len(pages):
            return []
        return pages[pagina - 1]


class _StubListaSuja:
    def __init__(self, rows: list[list[str | None]], fail: bool = False):
        self._rows = rows
        self._fail = fail

    def fetch_raw_rows(self) -> list[list[str | None]]:
        if self._fail:
            raise ProviderError("boom")
        return self._rows


def test_ingest_api_list_paginates_until_empty_page(db):
    portal = _StubPortal(
        {
            "ceis": [
                [_ceis_record(1, "11.111.111/0001-11")],
                [_ceis_record(2, "22.222.222/0001-22")],
            ]
        }
    )

    count = restrictive_list_ingestion.ingest_api_list(db, portal, "ceis", max_pages=10)

    assert count == 2
    assert portal.calls == [("ceis", 1), ("ceis", 2), ("ceis", 3)]


def test_ingest_api_list_respects_max_pages(db):
    portal = _StubPortal({"ceis": [[_ceis_record(1, "11.111.111/0001-11")]] * 5})

    restrictive_list_ingestion.ingest_api_list(db, portal, "ceis", max_pages=2)

    assert len(portal.calls) == 2


def test_ingest_leniencia_flattens_multiple_companies_per_agreement(db):
    portal = _StubPortal(
        {
            "leniencia": [
                [
                    {
                        "id": 1,
                        "situacaoAcordo": "Vigente",
                        "orgaoResponsavel": "CGU",
                        "dataInicioAcordo": None,
                        "dataFimAcordo": None,
                        "sancoes": [
                            {"razaoSocial": "A", "cnpjFormatado": "11.111.111/0001-11"},
                            {"razaoSocial": "B", "cnpjFormatado": "22.222.222/0001-22"},
                        ],
                    }
                ]
            ]
        }
    )

    count = restrictive_list_ingestion.ingest_leniencia(db, portal, max_pages=10)

    assert count == 2


def test_ingest_lista_suja_persists_parsed_rows(db):
    row = [
        "1",
        "2024",
        "SP",
        "41.297.068 NOME EXEMPLO",
        "41.297.068/0001-61",
        "ENDEREÇO",
        "2",
        "0000-0/00",
        "",
        "",
    ]
    provider = _StubListaSuja([row])

    count = restrictive_list_ingestion.ingest_lista_suja(db, provider)

    assert count == 1
    assert db.query(RestrictiveListEntry).filter_by(list_type="trabalho_escravo").count() == 1


def test_ingest_all_isolates_failures_between_sources(db):
    portal = _StubPortal(
        {
            "ceis": [[_ceis_record(1, "11.111.111/0001-11")]],
            "cnep": [[_ceis_record(2, "22.222.222/0001-22")]],
            "cepim": [],
            "leniencia": [],
        },
        fail_list="cnep",
    )
    lista_suja = _StubListaSuja([], fail=True)

    results = restrictive_list_ingestion.ingest_all(db, portal, lista_suja, max_pages=10)

    assert results["ceis"] == 1
    assert results["cnep"] == 0
    assert results["trabalho_escravo"] == 0
