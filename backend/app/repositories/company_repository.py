import uuid
from datetime import UTC, datetime, time

from sqlalchemy.orm import Session

from app.models import CnaeSecundario, Company, CompanyPartnership, Partnership, Person
from app.providers.base import RawCompanyData


def get_by_cnpj(db: Session, cnpj: str) -> Company | None:
    return db.query(Company).filter(Company.cnpj == cnpj).one_or_none()


def get_by_id(db: Session, company_id: uuid.UUID) -> Company | None:
    return db.query(Company).filter(Company.id == company_id).one_or_none()


def upsert_company_partnership(
    db: Session,
    subject_company_id: uuid.UUID,
    object_company_id: uuid.UUID,
    qualificacao: str | None,
) -> CompanyPartnership:
    """Get-or-create the subject-holds-a-stake-in-object edge.

    Unlike person partnerships, this isn't diffed against a full QSA resync
    in one pass (we only ever learn one such edge at a time, while expanding
    one company's PJ-type QSA entries), so there is no ended_at bookkeeping
    here yet.
    """
    edge = (
        db.query(CompanyPartnership)
        .filter(
            CompanyPartnership.subject_company_id == subject_company_id,
            CompanyPartnership.object_company_id == object_company_id,
        )
        .one_or_none()
    )
    if edge is None:
        edge = CompanyPartnership(
            subject_company_id=subject_company_id,
            object_company_id=object_company_id,
            qualificacao=qualificacao,
        )
        db.add(edge)
    else:
        edge.qualificacao = qualificacao
    db.flush()
    return edge


def _address_key(data: RawCompanyData) -> str | None:
    if not data.cep or not data.numero:
        return None
    return f"{data.cep}:{data.numero}".upper()


def upsert_from_provider(db: Session, data: RawCompanyData) -> Company:
    """Persist a freshly-fetched dossier, diffing the QSA against prior partnerships.

    New partners get a fresh `partnerships` row, with first_seen_at set to
    Receita's own data_entrada_sociedade when available (falling back to now)
    so the QSA-churn risk rule measures real turnover, not our scrape cadence.
    Partners no longer present get `ended_at` set instead of being deleted,
    so the row stays as history for that same rule.
    """
    company = get_by_cnpj(db, data.cnpj)
    now = datetime.now(UTC)

    if company is None:
        company = Company(cnpj=data.cnpj)
        db.add(company)

    company.razao_social = data.razao_social
    company.nome_fantasia = data.nome_fantasia
    company.situacao_cadastral = data.situacao_cadastral
    company.situacao_cadastral_data = data.situacao_cadastral_data
    company.data_abertura = data.data_abertura
    company.capital_social = data.capital_social
    company.natureza_juridica_codigo = data.natureza_juridica_codigo
    company.natureza_juridica_descricao = data.natureza_juridica_descricao
    company.porte = data.porte
    company.cnae_principal_codigo = data.cnae_principal_codigo
    company.cnae_principal_descricao = data.cnae_principal_descricao
    company.logradouro = data.logradouro
    company.numero = data.numero
    company.complemento = data.complemento
    company.bairro = data.bairro
    company.municipio = data.municipio
    company.uf = data.uf
    company.cep = data.cep
    company.address_key = _address_key(data)
    company.source_provider = data.source_provider
    company.source_collected_at = now
    company.raw_response = data.raw_response

    company.cnaes_secundarios.clear()
    for cnae in data.cnaes_secundarios:
        company.cnaes_secundarios.append(
            CnaeSecundario(codigo=cnae.codigo, descricao=cnae.descricao)
        )

    db.flush()  # assigns company.id for new rows before the QSA diff below
    _sync_partnerships(db, company, data)

    return company


def _sync_partnerships(db: Session, company: Company, data: RawCompanyData) -> None:
    """Syncs person partners only.

    Pessoa-jurídica partners (tipo_socio == "pessoa_juridica") are not
    persisted here: turning one into a company_partnerships edge requires
    fetching that other CNPJ's own dossier first, which is graph-expansion
    work (Phase 2), not a plain single-company fetch.
    """
    now = datetime.now(UTC)
    active = {p.person_id: p for p in company.partnerships if p.ended_at is None}
    fetched_person_ids: set = set()

    person_partners = [p for p in data.partners if p.tipo_socio != "pessoa_juridica"]

    for partner in person_partners:
        person = (
            db.query(Person)
            .filter(Person.cpf_masked == partner.documento, Person.nome == partner.nome)
            .one_or_none()
        )
        if person is None:
            person = Person(
                cpf_masked=partner.documento, nome=partner.nome, faixa_etaria=partner.faixa_etaria
            )
            db.add(person)
            db.flush()
        else:
            person.faixa_etaria = partner.faixa_etaria

        fetched_person_ids.add(person.id)

        if person.id not in active:
            first_seen_at = (
                datetime.combine(partner.entrada_sociedade, time.min, tzinfo=UTC)
                if partner.entrada_sociedade
                else now
            )
            company.partnerships.append(
                Partnership(
                    person_id=person.id,
                    qualificacao=partner.qualificacao,
                    first_seen_at=first_seen_at,
                )
            )
        else:
            active[person.id].qualificacao = partner.qualificacao

    for person_id, partnership in active.items():
        if person_id not in fetched_person_ids:
            partnership.ended_at = now
