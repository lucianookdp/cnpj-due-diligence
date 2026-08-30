import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.risk import RiskScoreOut


class SecondaryCnaeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    descricao: str


class RestrictiveListMatchOut(BaseModel):
    list_type: str
    name: str
    reason: str | None
    source_org: str | None
    sanction_start_date: date | None
    sanction_end_date: date | None


class PartnerOut(BaseModel):
    nome: str
    cpf_masked: str | None
    faixa_etaria: str | None
    qualificacao: str | None
    restrictive_list_matches: list[RestrictiveListMatchOut]


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cnpj: str
    razao_social: str
    nome_fantasia: str | None
    situacao_cadastral: str
    situacao_cadastral_data: date | None
    data_abertura: date | None
    capital_social: Decimal | None
    natureza_juridica_codigo: str | None
    natureza_juridica_descricao: str | None
    porte: str | None
    cnae_principal_codigo: str | None
    cnae_principal_descricao: str | None
    cnaes_secundarios: list[SecondaryCnaeOut]
    logradouro: str | None
    numero: str | None
    complemento: str | None
    bairro: str | None
    municipio: str | None
    uf: str | None
    cep: str | None
    partners: list[PartnerOut]
    source_provider: str
    source_collected_at: datetime
    restrictive_list_matches: list[RestrictiveListMatchOut]
    risk_score: RiskScoreOut
