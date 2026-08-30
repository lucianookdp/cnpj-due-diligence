import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Company, CompanyPartnership, Partnership, Person
from app.repositories import graph_repository
from app.schemas.graph import GraphEdgeOut, GraphIndicatorsOut, GraphNodeOut


def _company_node(company: Company, shared_address_count: int | None) -> GraphNodeOut:
    return GraphNodeOut(
        id=company.id,
        node_type="company",
        label=company.razao_social,
        cnpj=company.cnpj,
        situacao_cadastral=company.situacao_cadastral,
        shared_address_company_count=shared_address_count,
    )


def _person_node(person: Person) -> GraphNodeOut:
    return GraphNodeOut(
        id=person.id, node_type="person", label=person.nome, faixa_etaria=person.faixa_etaria
    )


def _partnership_edge(partnership: Partnership) -> GraphEdgeOut:
    return GraphEdgeOut(
        id=partnership.id,
        source=partnership.person_id,
        target=partnership.company_id,
        edge_type="partnership",
        label=partnership.qualificacao,
    )


def _company_partnership_edge(edge: CompanyPartnership) -> GraphEdgeOut:
    return GraphEdgeOut(
        id=edge.id,
        source=edge.subject_company_id,
        target=edge.object_company_id,
        edge_type="company_partnership",
        label=edge.qualificacao,
    )


def render_subgraph(
    db: Session, node_ids: set[uuid.UUID], shared_address_threshold: int
) -> tuple[list[GraphNodeOut], list[GraphEdgeOut], GraphIndicatorsOut]:
    companies, people, partnerships, company_partnerships = graph_repository.get_subgraph(
        db, node_ids
    )

    address_keys = {c.address_key for c in companies if c.address_key}
    address_counts = graph_repository.count_companies_by_address_key(db, address_keys)
    shared_addresses = {
        key: count for key, count in address_counts.items() if count > shared_address_threshold
    }

    company_nodes = [
        _company_node(c, shared_addresses.get(c.address_key) if c.address_key else None)
        for c in companies
    ]
    person_nodes = [_person_node(p) for p in people]

    companies_per_person: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for partnership in partnerships:
        companies_per_person[partnership.person_id].add(partnership.company_id)
    shared_partner_ids = [
        person_id for person_id, linked in companies_per_person.items() if len(linked) >= 2
    ]

    edges = [_partnership_edge(p) for p in partnerships] + [
        _company_partnership_edge(cp) for cp in company_partnerships
    ]
    indicators = GraphIndicatorsOut(
        shared_partner_person_ids=shared_partner_ids, shared_address_keys=shared_addresses
    )

    return company_nodes + person_nodes, edges, indicators
