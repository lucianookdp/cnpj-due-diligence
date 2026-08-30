from app.models import CompanyPartnership, Person
from app.providers.base import CompanyNotFoundError, ProviderError, RawCompanyData, RawPartner
from app.providers.grafo_minha_receita import GraphRelation
from app.providers.receita_schema import parse_receita_payload
from app.repositories import company_repository
from app.services import graph_expansion

_IDENTIFICADOR_POR_TIPO_SOCIO = {"pessoa_juridica": 1, "pessoa_fisica": 2, "estrangeiro": 3}


def _raw(cnpj, partners: list[RawPartner] | None = None) -> RawCompanyData:
    """Builds a raw provider payload and runs it through the real parser, so
    company.raw_response (used by discover_from_company's re-parse) stays
    consistent with what production actually stores — a RawCompanyData
    assembled by hand here previously papered over a real bug: its
    raw_response didn't match its own partners list.
    """
    payload = {
        "cnpj": cnpj,
        "razao_social": f"EMPRESA {cnpj}",
        "nome_fantasia": None,
        "descricao_situacao_cadastral": "ATIVA",
        "data_situacao_cadastral": None,
        "data_inicio_atividade": None,
        "capital_social": None,
        "codigo_natureza_juridica": None,
        "natureza_juridica": None,
        "porte": None,
        "cnae_fiscal": None,
        "cnae_fiscal_descricao": None,
        "cnaes_secundarios": [],
        "logradouro": None,
        "numero": None,
        "complemento": None,
        "bairro": None,
        "municipio": None,
        "uf": None,
        "cep": None,
        "qsa": [
            {
                "nome_socio": p.nome,
                "cnpj_cpf_do_socio": p.documento,
                "identificador_de_socio": _IDENTIFICADOR_POR_TIPO_SOCIO[p.tipo_socio],
                "faixa_etaria": p.faixa_etaria,
                "qualificacao_socio": p.qualificacao,
            }
            for p in (partners or [])
        ],
    }
    return parse_receita_payload(payload, source_provider="minha_receita")


class _StubResolver:
    def __init__(self, data_by_cnpj: dict[str, RawCompanyData]):
        self._data = data_by_cnpj
        self.calls: list[str] = []

    def fetch_company(self, cnpj: str) -> RawCompanyData:
        self.calls.append(cnpj)
        if cnpj not in self._data:
            raise CompanyNotFoundError(cnpj)
        return self._data[cnpj]


class _StubGrafo:
    def __init__(self, relations_by_ref: dict[str, list[GraphRelation]]):
        self._relations = relations_by_ref
        self.calls: list[str] = []

    def fetch_relations(self, ref: str) -> list[GraphRelation]:
        self.calls.append(ref)
        if ref not in self._relations:
            raise ProviderError(f"no relations for {ref}")
        return self._relations[ref]


def _persist(db, raw: RawCompanyData):
    company = company_repository.upsert_from_provider(db, raw)
    db.flush()
    return company


def test_discover_from_company_follows_pessoa_juridica_partner(db):
    pj_partner = RawPartner(
        nome="HOLDING E",
        documento="22222222000102",
        tipo_socio="pessoa_juridica",
        faixa_etaria=None,
        qualificacao="Sócio",
        entrada_sociedade=None,
    )
    company_a = _persist(db, _raw("11111111000101", partners=[pj_partner]))
    resolver = _StubResolver({"22222222000102": _raw("22222222000102")})
    grafo = _StubGrafo({})

    discovered = graph_expansion.discover_from_company(
        db,
        resolver,
        grafo,
        company_a,
        max_nodes_per_level=10,
        max_partner_lookups_per_company=10,
        cache_ttl_hours=720,
    )

    assert [c.cnpj for c in discovered] == ["22222222000102"]
    edge = db.query(CompanyPartnership).one()
    assert edge.subject_company_id == discovered[0].id
    assert edge.object_company_id == company_a.id


def test_discover_from_company_follows_person_via_reverse_lookup(db):
    person_partner = RawPartner(
        nome="FULANO",
        documento="***123456**",
        tipo_socio="pessoa_fisica",
        faixa_etaria="31 a 40 anos",
        qualificacao="Sócio",
        entrada_sociedade=None,
    )
    company_a = _persist(db, _raw("11111111000101", partners=[person_partner]))
    resolver = _StubResolver({"22222222000102": _raw("22222222000102")})
    grafo = _StubGrafo(
        {
            "11111111000101": [
                GraphRelation(
                    cnpj="11111111000101",
                    razao_social="A",
                    graph_ref_id="ref1",
                    nome="FULANO",
                    cpf_masked="***123456**",
                )
            ],
            "ref1": [
                GraphRelation(
                    cnpj="11111111000101",
                    razao_social="A",
                    graph_ref_id="ref1",
                    nome="FULANO",
                    cpf_masked="***123456**",
                ),
                GraphRelation(
                    cnpj="22222222000102",
                    razao_social="B",
                    graph_ref_id="ref1",
                    nome="FULANO",
                    cpf_masked="***123456**",
                ),
            ],
        }
    )

    discovered = graph_expansion.discover_from_company(
        db,
        resolver,
        grafo,
        company_a,
        max_nodes_per_level=10,
        max_partner_lookups_per_company=10,
        cache_ttl_hours=720,
    )

    assert [c.cnpj for c in discovered] == ["22222222000102"]
    person = db.query(Person).filter(Person.nome == "FULANO").one()
    assert person.graph_ref_id == "ref1"


def test_discover_from_company_respects_node_budget(db):
    partners = [
        RawPartner(
            nome=f"HOLDING {i}",
            documento=f"2222222200010{i}",
            tipo_socio="pessoa_juridica",
            faixa_etaria=None,
            qualificacao="Sócio",
            entrada_sociedade=None,
        )
        for i in range(3)
    ]
    company_a = _persist(db, _raw("11111111000101", partners=partners))
    resolver = _StubResolver({f"2222222200010{i}": _raw(f"2222222200010{i}") for i in range(3)})
    grafo = _StubGrafo({})

    discovered = graph_expansion.discover_from_company(
        db,
        resolver,
        grafo,
        company_a,
        max_nodes_per_level=1,
        max_partner_lookups_per_company=10,
        cache_ttl_hours=720,
    )

    assert len(discovered) == 1


def test_discover_from_company_respects_partner_lookup_cap(db):
    person_partners = [
        RawPartner(
            nome=f"PESSOA {i}",
            documento=f"***12345{i}**",
            tipo_socio="pessoa_fisica",
            faixa_etaria=None,
            qualificacao="Sócio",
            entrada_sociedade=None,
        )
        for i in range(3)
    ]
    company_a = _persist(db, _raw("11111111000101", partners=person_partners))
    resolver = _StubResolver({})
    grafo = _StubGrafo(
        {
            "11111111000101": [
                GraphRelation(
                    cnpj="11111111000101",
                    razao_social="A",
                    graph_ref_id=f"ref{i}",
                    nome=f"PESSOA {i}",
                    cpf_masked=f"***12345{i}**",
                )
                for i in range(3)
            ],
            "ref0": [],
            "ref1": [],
            "ref2": [],
        }
    )

    graph_expansion.discover_from_company(
        db,
        resolver,
        grafo,
        company_a,
        max_nodes_per_level=10,
        max_partner_lookups_per_company=1,
        cache_ttl_hours=720,
    )

    # One call to learn refs (by company cnpj) + at most 1 reverse-lookup call.
    assert grafo.calls.count("11111111000101") == 1
    assert sum(1 for c in grafo.calls if c.startswith("ref")) == 1


def test_discover_from_person_learns_graph_ref_id_from_existing_partnership(db):
    person_partner = RawPartner(
        nome="FULANO",
        documento="***123456**",
        tipo_socio="pessoa_fisica",
        faixa_etaria=None,
        qualificacao="Sócio",
        entrada_sociedade=None,
    )
    _persist(db, _raw("11111111000101", partners=[person_partner]))
    person = db.query(Person).filter(Person.nome == "FULANO").one()
    resolver = _StubResolver({"22222222000102": _raw("22222222000102")})
    grafo = _StubGrafo(
        {
            "11111111000101": [
                GraphRelation(
                    cnpj="11111111000101",
                    razao_social="A",
                    graph_ref_id="ref1",
                    nome="FULANO",
                    cpf_masked="***123456**",
                )
            ],
            "ref1": [
                GraphRelation(
                    cnpj="22222222000102",
                    razao_social="B",
                    graph_ref_id="ref1",
                    nome="FULANO",
                    cpf_masked="***123456**",
                )
            ],
        }
    )

    discovered = graph_expansion.discover_from_person(
        db, resolver, grafo, person, max_nodes=10, cache_ttl_hours=720
    )

    assert [c.cnpj for c in discovered] == ["22222222000102"]
    assert person.graph_ref_id == "ref1"


def test_discover_multi_level_bfs_respects_depth(db):
    pj_e = RawPartner(
        nome="E",
        documento="22222222000102",
        tipo_socio="pessoa_juridica",
        faixa_etaria=None,
        qualificacao="Sócio",
        entrada_sociedade=None,
    )
    pj_f = RawPartner(
        nome="F",
        documento="33333333000103",
        tipo_socio="pessoa_juridica",
        faixa_etaria=None,
        qualificacao="Sócio",
        entrada_sociedade=None,
    )
    resolver = _StubResolver(
        {
            "11111111000101": _raw("11111111000101", partners=[pj_e]),
            "22222222000102": _raw("22222222000102", partners=[pj_f]),
            "33333333000103": _raw("33333333000103"),
        }
    )
    grafo = _StubGrafo({})

    graph_expansion.discover(
        db,
        resolver,
        grafo,
        "11111111000101",
        depth=1,
        max_nodes_per_level=10,
        max_partner_lookups_per_company=10,
        cache_ttl_hours=720,
    )
    assert company_repository.get_by_cnpj(db, "33333333000103") is None

    graph_expansion.discover(
        db,
        resolver,
        grafo,
        "11111111000101",
        depth=2,
        max_nodes_per_level=10,
        max_partner_lookups_per_company=10,
        cache_ttl_hours=720,
    )
    assert company_repository.get_by_cnpj(db, "33333333000103") is not None
