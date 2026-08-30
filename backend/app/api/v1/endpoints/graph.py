import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_grafo_provider, get_resolver
from app.core.cnpj import InvalidCnpjError, normalize_cnpj
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.rate_limit import rate_limit
from app.models import Person
from app.providers.grafo_minha_receita import GrafoMinhaReceitaProvider
from app.providers.resolver import ProviderResolver
from app.repositories import company_repository, graph_repository
from app.schemas.graph import GraphDeltaOut, GraphOut
from app.services import graph_expansion, graph_view
from app.services.dossier import DossierNotFoundError

router = APIRouter()


@router.get(
    "/graph/{cnpj}",
    response_model=GraphOut,
    # Tighter than a plain dossier lookup — one call can trigger several
    # outbound fetches (grafo reverse-lookups plus a dossier fetch per newly
    # discovered company), even though each of those is itself bounded.
    dependencies=[Depends(rate_limit(max_requests=15, window_seconds=60))],
)
def read_graph(
    cnpj: str,
    depth: int | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    resolver: ProviderResolver = Depends(get_resolver),
    grafo: GrafoMinhaReceitaProvider = Depends(get_grafo_provider),
) -> GraphOut:
    try:
        normalized = normalize_cnpj(cnpj)
    except InvalidCnpjError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    company_depth = depth if depth is not None else settings.graph_max_depth

    try:
        root = graph_expansion.discover(
            db,
            resolver,
            grafo,
            normalized,
            depth=company_depth,
            max_nodes_per_level=settings.graph_max_nodes_per_level,
            max_partner_lookups_per_company=settings.graph_max_partner_lookups_per_company,
            cache_ttl_hours=settings.cache_ttl_hours,
        )
    except DossierNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"CNPJ {normalized} não encontrado") from exc

    # Each "company level" of discovery is up to 2 raw graph edges when the hop
    # goes through a person (company -> person -> company), only 1 when it's a
    # direct company_partnerships edge — so the recursive read below must walk
    # twice as many raw edges as the discovery depth to actually reach what was
    # just discovered.
    node_ids = graph_repository.get_reachable_node_ids(
        db,
        root.id,
        max_depth=company_depth * 2,
        max_nodes=settings.graph_max_nodes_per_level * (company_depth + 1),
    )
    nodes, edges, indicators = graph_view.render_subgraph(
        db, node_ids, settings.shared_address_threshold
    )

    return GraphOut(root_cnpj=normalized, nodes=nodes, edges=edges, indicators=indicators)


@router.post(
    "/graph/expand/company/{company_id}",
    response_model=GraphDeltaOut,
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60))],
)
def expand_company_node(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    resolver: ProviderResolver = Depends(get_resolver),
    grafo: GrafoMinhaReceitaProvider = Depends(get_grafo_provider),
) -> GraphDeltaOut:
    company = company_repository.get_by_id(db, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Nó de empresa {company_id} não encontrado")

    discovered = graph_expansion.discover_from_company(
        db,
        resolver,
        grafo,
        company,
        max_nodes_per_level=settings.graph_max_nodes_per_level,
        max_partner_lookups_per_company=settings.graph_max_partner_lookups_per_company,
        cache_ttl_hours=settings.cache_ttl_hours,
    )

    node_ids = {company.id} | {c.id for c in discovered}
    nodes, edges, _ = graph_view.render_subgraph(db, node_ids, settings.shared_address_threshold)
    return GraphDeltaOut(nodes=nodes, edges=edges)


@router.post(
    "/graph/expand/person/{person_id}",
    response_model=GraphDeltaOut,
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60))],
)
def expand_person_node(
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    resolver: ProviderResolver = Depends(get_resolver),
    grafo: GrafoMinhaReceitaProvider = Depends(get_grafo_provider),
) -> GraphDeltaOut:
    person = db.query(Person).filter(Person.id == person_id).one_or_none()
    if person is None:
        raise HTTPException(status_code=404, detail=f"Nó de pessoa {person_id} não encontrado")

    discovered = graph_expansion.discover_from_person(
        db,
        resolver,
        grafo,
        person,
        max_nodes=settings.graph_max_nodes_per_level,
        cache_ttl_hours=settings.cache_ttl_hours,
    )

    node_ids = {person.id} | {c.id for c in discovered}
    nodes, edges, _ = graph_view.render_subgraph(db, node_ids, settings.shared_address_threshold)
    return GraphDeltaOut(nodes=nodes, edges=edges)
