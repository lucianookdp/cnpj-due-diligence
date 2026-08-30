from sqlalchemy.orm import Session

from app.models import Company, Person
from app.providers.base import ProviderError
from app.providers.grafo_minha_receita import GrafoMinhaReceitaProvider
from app.providers.receita_schema import parse_receita_payload
from app.providers.resolver import ProviderResolver
from app.repositories import company_repository
from app.services.dossier import DossierNotFoundError, ensure_company


def discover(
    db: Session,
    resolver: ProviderResolver,
    grafo: GrafoMinhaReceitaProvider,
    root_cnpj: str,
    depth: int,
    max_nodes_per_level: int,
    max_partner_lookups_per_company: int,
    cache_ttl_hours: int,
) -> Company:
    """Fetches root_cnpj and BFS-expands its graph up to depth levels.

    Bounded by max_nodes_per_level per level and max_partner_lookups_per_company
    (grafo.minhareceita.org reverse-lookup calls) per company — both exist
    because a single large company can have dozens of officers, each
    potentially linked to dozens more companies.
    """
    root = ensure_company(db, resolver, root_cnpj, cache_ttl_hours)
    visited_cnpjs = {root.cnpj}
    frontier = [root]

    for _ in range(depth):
        next_frontier: list[Company] = []
        budget = max_nodes_per_level

        for company in frontier:
            if budget <= 0:
                break
            discovered = discover_from_company(
                db,
                resolver,
                grafo,
                company,
                max_nodes_per_level=budget,
                max_partner_lookups_per_company=max_partner_lookups_per_company,
                cache_ttl_hours=cache_ttl_hours,
                exclude_cnpjs=visited_cnpjs,
            )
            for neighbor in discovered:
                if neighbor.cnpj in visited_cnpjs:
                    continue
                visited_cnpjs.add(neighbor.cnpj)
                next_frontier.append(neighbor)
                budget -= 1

        frontier = next_frontier
        if not frontier:
            break

    return root


def discover_from_company(
    db: Session,
    resolver: ProviderResolver,
    grafo: GrafoMinhaReceitaProvider,
    company: Company,
    max_nodes_per_level: int,
    max_partner_lookups_per_company: int,
    cache_ttl_hours: int,
    exclude_cnpjs: set[str] | None = None,
) -> list[Company]:
    """Expands exactly one company node: its PJ-type QSA entries directly, and its
    person partners via grafo.minhareceita.org's reverse lookup. Used both by the
    root-to-depth BFS above and by the "expand this node" API for on-demand clicks.
    """
    exclude = exclude_cnpjs or set()
    data = parse_receita_payload(company.raw_response, company.source_provider)

    discovered: list[Company] = []
    seen_this_call: set[str] = set()

    pj_partners = [p for p in data.partners if p.tipo_socio == "pessoa_juridica" and p.documento]
    for partner in pj_partners:
        if len(discovered) >= max_nodes_per_level:
            break
        candidate_cnpj = partner.documento
        if (
            candidate_cnpj in exclude
            or candidate_cnpj in seen_this_call
            or candidate_cnpj == company.cnpj
        ):
            continue
        try:
            neighbor = ensure_company(db, resolver, candidate_cnpj, cache_ttl_hours)
        except DossierNotFoundError:
            continue
        seen_this_call.add(candidate_cnpj)
        discovered.append(neighbor)
        company_repository.upsert_company_partnership(
            db,
            subject_company_id=neighbor.id,
            object_company_id=company.id,
            qualificacao=partner.qualificacao,
        )

    person_partners = [p for p in data.partners if p.tipo_socio != "pessoa_juridica"]
    if person_partners and len(discovered) < max_nodes_per_level:
        for candidate_cnpj in _discover_via_reverse_lookup(
            db, grafo, company, person_partners, max_partner_lookups_per_company
        ):
            if len(discovered) >= max_nodes_per_level:
                break
            if (
                candidate_cnpj in exclude
                or candidate_cnpj in seen_this_call
                or candidate_cnpj == company.cnpj
            ):
                continue
            try:
                neighbor = ensure_company(db, resolver, candidate_cnpj, cache_ttl_hours)
            except DossierNotFoundError:
                continue
            seen_this_call.add(candidate_cnpj)
            discovered.append(neighbor)

    return discovered


def _discover_via_reverse_lookup(
    db: Session,
    grafo: GrafoMinhaReceitaProvider,
    company: Company,
    person_partners: list,
    max_lookups: int,
) -> list[str]:
    try:
        relations = grafo.fetch_relations(company.cnpj)
    except ProviderError:
        return []

    ref_by_identity = {(r.cpf_masked, r.nome): r.graph_ref_id for r in relations}

    candidate_cnpjs: list[str] = []
    lookups_done = 0
    for partner in person_partners:
        if lookups_done >= max_lookups:
            break
        person = (
            db.query(Person)
            .filter(Person.cpf_masked == partner.documento, Person.nome == partner.nome)
            .one_or_none()
        )
        if person is None:
            continue

        if person.graph_ref_id is None:
            graph_ref_id = ref_by_identity.get((partner.documento, partner.nome))
            if graph_ref_id is None:
                continue
            person.graph_ref_id = graph_ref_id
            db.flush()

        lookups_done += 1
        try:
            other_relations = grafo.fetch_relations(person.graph_ref_id)
        except ProviderError:
            continue

        candidate_cnpjs.extend(r.cnpj for r in other_relations if r.cnpj != company.cnpj)

    return candidate_cnpjs


def discover_from_person(
    db: Session,
    resolver: ProviderResolver,
    grafo: GrafoMinhaReceitaProvider,
    person: Person,
    max_nodes: int,
    cache_ttl_hours: int,
) -> list[Company]:
    """Expands a person node directly: every other company they're linked to."""
    if person.graph_ref_id is None:
        active_partnership = next((p for p in person.partnerships if p.ended_at is None), None)
        if active_partnership is None:
            return []
        try:
            relations = grafo.fetch_relations(active_partnership.company.cnpj)
        except ProviderError:
            return []
        match = next(
            (r for r in relations if r.cpf_masked == person.cpf_masked and r.nome == person.nome),
            None,
        )
        if match is None:
            return []
        person.graph_ref_id = match.graph_ref_id
        db.flush()

    try:
        relations = grafo.fetch_relations(person.graph_ref_id)
    except ProviderError:
        return []

    discovered: list[Company] = []
    for relation in relations:
        if len(discovered) >= max_nodes:
            break
        try:
            discovered.append(ensure_company(db, resolver, relation.cnpj, cache_ttl_hours))
        except DossierNotFoundError:
            continue
    return discovered
