from sqlalchemy.orm import Session

from app.core.document import mask_cpf
from app.models import RestrictiveListEntry


def match_by_cnpj(db: Session, cnpj: str) -> list[RestrictiveListEntry]:
    return (
        db.query(RestrictiveListEntry)
        .filter(RestrictiveListEntry.document == cnpj, RestrictiveListEntry.document_type == "cnpj")
        .all()
    )


def match_by_masked_cpf(db: Session, cpf_masked: str | None) -> list[RestrictiveListEntry]:
    """Restrictive lists publish full CPFs; our own people are stored Receita-masked.

    Re-derives the same mask from each cpf-type entry and compares — an O(n)
    scan over cpf-type entries, acceptable at this dataset's size (low
    thousands), revisit with a stored masked-document column if it grows.
    """
    if cpf_masked is None:
        return []
    candidates = (
        db.query(RestrictiveListEntry).filter(RestrictiveListEntry.document_type == "cpf").all()
    )
    return [c for c in candidates if mask_cpf(c.document) == cpf_masked]
