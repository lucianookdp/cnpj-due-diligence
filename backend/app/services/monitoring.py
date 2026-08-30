from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Company
from app.services import restrictive_list_matching


@dataclass(frozen=True)
class CompanySnapshot:
    situacao_cadastral: str
    active_partner_keys: frozenset[tuple[str | None, str]]
    restrictive_match_keys: frozenset[tuple[str, str]]


def snapshot(db: Session, company: Company) -> CompanySnapshot:
    active_partners = frozenset(
        (p.person.cpf_masked, p.person.nome) for p in company.partnerships if p.ended_at is None
    )

    matches = list(restrictive_list_matching.match_by_cnpj(db, company.cnpj))
    for partnership in company.partnerships:
        if partnership.ended_at is None:
            matches.extend(
                restrictive_list_matching.match_by_masked_cpf(db, partnership.person.cpf_masked)
            )
    match_keys = frozenset((m.list_type, m.external_id) for m in matches)

    return CompanySnapshot(
        situacao_cadastral=company.situacao_cadastral,
        active_partner_keys=active_partners,
        restrictive_match_keys=match_keys,
    )


def detect_changes(before: CompanySnapshot, after: CompanySnapshot) -> list[tuple[str, str]]:
    """Returns (alert_type, message) pairs — the three change types the spec calls out:
    baixa na Receita, entrada em lista, troca de sócio.
    """
    changes: list[tuple[str, str]] = []

    if before.situacao_cadastral != after.situacao_cadastral:
        message = (
            f"Situação cadastral mudou de '{before.situacao_cadastral}' para "
            f"'{after.situacao_cadastral}'"
        )
        changes.append(("situacao_alterada", message))

    new_matches = after.restrictive_match_keys - before.restrictive_match_keys
    if new_matches:
        list_types = sorted({lt.upper() for lt, _ in new_matches})
        changes.append(
            (
                "nova_lista_restritiva",
                f"Nova(s) entrada(s) em lista restritiva: {', '.join(list_types)}",
            )
        )

    if before.active_partner_keys != after.active_partner_keys:
        added = after.active_partner_keys - before.active_partner_keys
        removed = before.active_partner_keys - after.active_partner_keys
        parts = []
        if added:
            parts.append(f"{len(added)} sócio(s) incluído(s)")
        if removed:
            parts.append(f"{len(removed)} sócio(s) removido(s)")
        changes.append(("socio_alterado", "Quadro societário alterado: " + ", ".join(parts)))

    return changes
