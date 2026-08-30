from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

# Per Receita's official CNPJ open-data layout ("identificador de sócio"):
# 1 = Pessoa Jurídica, 2 = Pessoa Física, 3 = Estrangeiro (no CPF/CNPJ at all).
TipoSocio = Literal["pessoa_juridica", "pessoa_fisica", "estrangeiro"]


@dataclass
class RawPartner:
    nome: str
    documento: str | None
    """Masked CPF for pessoa_fisica, full CNPJ for pessoa_juridica, None for estrangeiro."""
    tipo_socio: TipoSocio
    faixa_etaria: str | None
    qualificacao: str | None
    entrada_sociedade: date | None
    """Real QSA entry date from Receita — used as Partnership.first_seen_at so
    the QSA-churn risk rule measures actual turnover, not when we happened to
    first scrape this company."""


@dataclass
class RawSecondaryCnae:
    codigo: str
    descricao: str


@dataclass
class RawCompanyData:
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
    cnaes_secundarios: list[RawSecondaryCnae]
    logradouro: str | None
    numero: str | None
    complemento: str | None
    bairro: str | None
    municipio: str | None
    uf: str | None
    cep: str | None
    partners: list[RawPartner]
    source_provider: str
    raw_response: dict


class ProviderError(Exception):
    """Raised when a provider fails to answer (network error, timeout, 5xx)."""


class CompanyNotFoundError(Exception):
    """Raised when the provider affirmatively reports the CNPJ does not exist."""


class CompanyDataProvider(Protocol):
    name: str

    def fetch_company(self, cnpj: str) -> RawCompanyData:
        """Fetch and normalize company data for cnpj.

        Raises CompanyNotFoundError if the source reports no such CNPJ, or
        ProviderError for any other failure (network, timeout, unexpected shape).
        """
        ...
