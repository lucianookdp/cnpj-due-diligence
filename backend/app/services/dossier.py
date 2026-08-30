from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rules_config import load_rules_config
from app.models import Company, RestrictiveListEntry
from app.providers.base import CompanyNotFoundError
from app.providers.resolver import ProviderResolver
from app.repositories import company_repository
from app.schemas.company import CompanyOut, PartnerOut, RestrictiveListMatchOut, SecondaryCnaeOut
from app.schemas.risk import RiskScoreOut, RuleResultOut
from app.services import restrictive_list_matching, risk_scoring


class DossierNotFoundError(Exception):
    pass


def get_dossier(
    db: Session,
    resolver: ProviderResolver,
    cnpj: str,
    cache_ttl_hours: int,
    expected_activity_description: str | None = None,
) -> CompanyOut:
    company = ensure_company(db, resolver, cnpj, cache_ttl_hours)
    return _to_schema(db, company, expected_activity_description)


def ensure_company(
    db: Session,
    resolver: ProviderResolver,
    cnpj: str,
    cache_ttl_hours: int,
) -> Company:
    """Returns the ORM row for cnpj, fetching from providers only on a cache miss/expiry.

    Shared by the plain dossier endpoint and graph expansion (Phase 2), which
    needs the ORM object — not the pydantic schema — to read raw_response and
    chain further traversal off of company.id.
    """
    company = company_repository.get_by_cnpj(db, cnpj)

    if company is None or _is_stale(company, cache_ttl_hours):
        try:
            raw = resolver.fetch_company(cnpj)
        except CompanyNotFoundError as exc:
            raise DossierNotFoundError(cnpj) from exc
        try:
            company = company_repository.upsert_from_provider(db, raw)
            db.commit()
        except IntegrityError:
            # Graph discovery can reach the same CNPJ from two different
            # paths in concurrent requests (or the root dossier and root
            # graph fetch racing each other); Postgres's unique constraint
            # only raises this once the other transaction has committed, so
            # a plain re-fetch here is guaranteed to find its row.
            db.rollback()
            company = company_repository.get_by_cnpj(db, cnpj)
            if company is None:
                raise

    return company


def _is_stale(company: Company, cache_ttl_hours: int) -> bool:
    collected_at = company.source_collected_at
    if collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - collected_at > timedelta(hours=cache_ttl_hours)


def _match_out(entries: list[RestrictiveListEntry]) -> list[RestrictiveListMatchOut]:
    return [
        RestrictiveListMatchOut(
            list_type=e.list_type,
            name=e.name,
            reason=e.reason,
            source_org=e.source_org,
            sanction_start_date=e.sanction_start_date,
            sanction_end_date=e.sanction_end_date,
        )
        for e in entries
    ]


def _risk_score_out(
    db: Session, company: Company, expected_activity_description: str | None
) -> RiskScoreOut:
    ctx = risk_scoring.build_context(db, company, expected_activity_description)
    result = risk_scoring.evaluate(ctx, load_rules_config())
    return RiskScoreOut(
        score=result.score,
        rules_version=result.rules_version,
        results=[
            RuleResultOut(
                rule_id=r.rule_id,
                label=r.label,
                weight=r.weight,
                triggered=r.triggered,
                reason=r.reason,
            )
            for r in result.results
        ],
    )


def _to_schema(
    db: Session, company: Company, expected_activity_description: str | None = None
) -> CompanyOut:
    active_partners = [
        PartnerOut(
            nome=p.person.nome,
            cpf_masked=p.person.cpf_masked,
            faixa_etaria=p.person.faixa_etaria,
            qualificacao=p.qualificacao,
            restrictive_list_matches=_match_out(
                restrictive_list_matching.match_by_masked_cpf(db, p.person.cpf_masked)
            ),
        )
        for p in company.partnerships
        if p.ended_at is None
    ]
    return CompanyOut(
        id=company.id,
        cnpj=company.cnpj,
        razao_social=company.razao_social,
        nome_fantasia=company.nome_fantasia,
        situacao_cadastral=company.situacao_cadastral,
        situacao_cadastral_data=company.situacao_cadastral_data,
        data_abertura=company.data_abertura,
        capital_social=company.capital_social,
        natureza_juridica_codigo=company.natureza_juridica_codigo,
        natureza_juridica_descricao=company.natureza_juridica_descricao,
        porte=company.porte,
        cnae_principal_codigo=company.cnae_principal_codigo,
        cnae_principal_descricao=company.cnae_principal_descricao,
        cnaes_secundarios=[
            SecondaryCnaeOut(codigo=c.codigo, descricao=c.descricao)
            for c in company.cnaes_secundarios
        ],
        logradouro=company.logradouro,
        numero=company.numero,
        complemento=company.complemento,
        bairro=company.bairro,
        municipio=company.municipio,
        uf=company.uf,
        cep=company.cep,
        partners=active_partners,
        source_provider=company.source_provider,
        source_collected_at=company.source_collected_at,
        restrictive_list_matches=_match_out(
            restrictive_list_matching.match_by_cnpj(db, company.cnpj)
        ),
        risk_score=_risk_score_out(db, company, expected_activity_description),
    )
