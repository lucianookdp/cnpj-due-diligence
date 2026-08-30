import uuid
from collections import Counter

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Company, CompanyPartnership, Partnership, Person

# UNIONs both edge tables (each direction) so the recursive walk doesn't care
# whether a hop is person<->company or company<->company; only active
# (ended_at IS NULL) edges count towards the current graph shape.
_REACHABLE_NODE_IDS_SQL = text("""
    WITH RECURSIVE edges(a, b) AS (
        SELECT person_id, company_id FROM partnerships WHERE ended_at IS NULL
        UNION ALL
        SELECT company_id, person_id FROM partnerships WHERE ended_at IS NULL
        UNION ALL
        SELECT subject_company_id, object_company_id FROM company_partnerships WHERE ended_at IS NULL
        UNION ALL
        SELECT object_company_id, subject_company_id FROM company_partnerships WHERE ended_at IS NULL
    ),
    reachable(node_id, depth) AS (
        SELECT CAST(:root_id AS uuid), 0
        UNION
        SELECT e.b, r.depth + 1
        FROM edges e
        JOIN reachable r ON e.a = r.node_id
        WHERE r.depth < :max_depth
    )
    SELECT DISTINCT node_id FROM reachable LIMIT :max_nodes
""")


def get_reachable_node_ids(
    db: Session, root_id: uuid.UUID, max_depth: int, max_nodes: int
) -> set[uuid.UUID]:
    rows = db.execute(
        _REACHABLE_NODE_IDS_SQL,
        {"root_id": str(root_id), "max_depth": max_depth, "max_nodes": max_nodes},
    )
    return {row[0] for row in rows}


def get_subgraph(
    db: Session, node_ids: set[uuid.UUID]
) -> tuple[list[Company], list[Person], list[Partnership], list[CompanyPartnership]]:
    if not node_ids:
        return [], [], [], []

    companies = db.query(Company).filter(Company.id.in_(node_ids)).all()
    people = db.query(Person).filter(Person.id.in_(node_ids)).all()
    partnerships = (
        db.query(Partnership)
        .filter(
            Partnership.ended_at.is_(None),
            Partnership.company_id.in_(node_ids),
            Partnership.person_id.in_(node_ids),
        )
        .all()
    )
    company_partnerships = (
        db.query(CompanyPartnership)
        .filter(
            CompanyPartnership.ended_at.is_(None),
            CompanyPartnership.subject_company_id.in_(node_ids),
            CompanyPartnership.object_company_id.in_(node_ids),
        )
        .all()
    )
    return companies, people, partnerships, company_partnerships


def count_companies_by_address_key(db: Session, address_keys: set[str]) -> Counter:
    """Global counts (not just within one rendered subgraph) — a shared address is a
    red flag about the address itself, independent of which query happened to surface it.
    """
    if not address_keys:
        return Counter()
    rows = (
        db.query(Company.address_key, Company.id)
        .filter(Company.address_key.in_(address_keys))
        .all()
    )
    return Counter(row[0] for row in rows)
