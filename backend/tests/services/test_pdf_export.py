import uuid
from datetime import UTC, datetime

from app.core.config import Settings
from app.models import Company, Partnership, Person
from app.schemas.company import CompanyOut
from app.schemas.graph import GraphEdgeOut, GraphNodeOut
from app.schemas.risk import RiskScoreOut, RuleResultOut
from app.services.pdf_export import _cap_nodes_for_pdf, render_dossier_pdf


def _company_out(company_id: uuid.UUID | None = None, score: int = 0) -> CompanyOut:
    return CompanyOut(
        id=company_id or uuid.uuid4(),
        cnpj="11222333000181",
        razao_social="EMPRESA TESTE LTDA",
        nome_fantasia=None,
        situacao_cadastral="ATIVA",
        situacao_cadastral_data=None,
        data_abertura=None,
        capital_social=None,
        natureza_juridica_codigo=None,
        natureza_juridica_descricao=None,
        porte=None,
        cnae_principal_codigo="6201500",
        cnae_principal_descricao="Desenvolvimento de programas de computador",
        cnaes_secundarios=[],
        logradouro="RUA TESTE",
        numero="100",
        complemento=None,
        bairro="CENTRO",
        municipio="SAO PAULO",
        uf="SP",
        cep="01310100",
        partners=[],
        source_provider="minha_receita",
        source_collected_at=datetime.now(UTC),
        restrictive_list_matches=[],
        risk_score=RiskScoreOut(
            score=score,
            rules_version=1,
            results=[
                RuleResultOut(
                    rule_id="situacao_cadastral_inativa",
                    label="Situação cadastral diferente de ativa",
                    weight=20,
                    triggered=score > 0,
                    reason="Situação cadastral é 'BAIXADA', não ATIVA" if score > 0 else None,
                )
            ],
        ),
    )


def test_renders_a_valid_pdf(db):
    pdf_bytes = render_dossier_pdf(db, _company_out(), Settings())

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_renders_high_risk_company_without_error(db):
    pdf_bytes = render_dossier_pdf(db, _company_out(score=100), Settings())

    assert pdf_bytes.startswith(b"%PDF")


def test_renders_graph_page_when_company_has_partners(db):
    company = Company(
        cnpj="11222333000181",
        razao_social="EMPRESA TESTE LTDA",
        situacao_cadastral="ATIVA",
        source_provider="minha_receita",
        source_collected_at=datetime.now(UTC),
        raw_response={},
    )
    db.add(company)
    db.flush()
    person = Person(cpf_masked="***111111**", nome="SOCIO TESTE")
    db.add(person)
    db.flush()
    db.add(Partnership(person_id=person.id, company_id=company.id, qualificacao="Sócio"))
    db.flush()

    pdf_bytes = render_dossier_pdf(db, _company_out(company_id=company.id), Settings())

    assert pdf_bytes.startswith(b"%PDF")
    # A real assertion that the graph page's content made it into the PDF
    # (not just "didn't crash") would need to parse the PDF text layer;
    # the length bump from the base case is a cheap proxy that the extra
    # page with the SVG actually got included.
    assert len(pdf_bytes) > 1500


def _node(node_type="company") -> GraphNodeOut:
    return GraphNodeOut(id=uuid.uuid4(), node_type=node_type, label="X")


def test_cap_nodes_for_pdf_is_a_noop_under_the_limit():
    root = _node()
    others = [_node() for _ in range(5)]
    edges = [
        GraphEdgeOut(id=uuid.uuid4(), source=root.id, target=o.id, edge_type="company_partnership")
        for o in others
    ]

    nodes, kept_edges, total = _cap_nodes_for_pdf([root, *others], edges, root.id)

    assert len(nodes) == 6
    assert total == 6
    assert kept_edges == edges


def test_cap_nodes_for_pdf_prioritizes_direct_neighbors_of_root():
    """A company with hundreds of indirectly-linked nodes (e.g. a bank with
    many branches) must still show the root's own direct partners first —
    those are the relationships a reader of the report actually cares about.
    """
    root = _node()
    direct = [_node() for _ in range(10)]
    indirect = [_node() for _ in range(100)]
    edges = [
        GraphEdgeOut(id=uuid.uuid4(), source=root.id, target=d.id, edge_type="company_partnership")
        for d in direct
    ] + [
        # indirect nodes connect to each other, never to root
        GraphEdgeOut(
            id=uuid.uuid4(),
            source=indirect[i].id,
            target=indirect[i + 1].id,
            edge_type="company_partnership",
        )
        for i in range(len(indirect) - 1)
    ]

    nodes, kept_edges, total = _cap_nodes_for_pdf([root, *direct, *indirect], edges, root.id)

    kept_ids = {n.id for n in nodes}
    assert total == 111
    assert len(nodes) == 40
    assert root.id in kept_ids
    assert all(d.id in kept_ids for d in direct)
    assert all(e.source in kept_ids and e.target in kept_ids for e in kept_edges)
