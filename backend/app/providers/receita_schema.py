"""Shared parsing for the Receita Federal open-data JSON shape.

Minha Receita and BrasilAPI both mirror the same underlying dataset column
names (cnae_fiscal, qsa, cnaes_secundarios, ...), confirmed by comparing live
responses from both APIs for the same CNPJ. A single parser covers both;
provider modules only differ in how they call their endpoint.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.providers.base import RawCompanyData, RawPartner, RawSecondaryCnae, TipoSocio

_TIPO_SOCIO_POR_IDENTIFICADOR: dict[int, TipoSocio] = {
    1: "pessoa_juridica",
    2: "pessoa_fisica",
    3: "estrangeiro",
}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()  # noqa: DTZ007 (date-only, no tz to attach)
    except ValueError:
        return None


def _parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def parse_receita_payload(payload: dict, source_provider: str) -> RawCompanyData:
    cnaes_secundarios = [
        RawSecondaryCnae(codigo=str(item["codigo"]), descricao=item["descricao"])
        for item in payload.get("cnaes_secundarios") or []
    ]

    partners = [
        RawPartner(
            nome=item["nome_socio"],
            documento=item.get("cnpj_cpf_do_socio"),
            tipo_socio=_TIPO_SOCIO_POR_IDENTIFICADOR.get(
                item.get("identificador_de_socio"), "pessoa_fisica"
            ),
            faixa_etaria=item.get("faixa_etaria"),
            qualificacao=item.get("qualificacao_socio"),
            entrada_sociedade=_parse_date(item.get("data_entrada_sociedade")),
        )
        for item in payload.get("qsa") or []
    ]

    return RawCompanyData(
        cnpj=payload["cnpj"],
        razao_social=payload["razao_social"],
        nome_fantasia=payload.get("nome_fantasia") or None,
        situacao_cadastral=payload["descricao_situacao_cadastral"],
        situacao_cadastral_data=_parse_date(payload.get("data_situacao_cadastral")),
        data_abertura=_parse_date(payload.get("data_inicio_atividade")),
        capital_social=_parse_decimal(payload.get("capital_social")),
        natureza_juridica_codigo=(
            str(payload["codigo_natureza_juridica"])
            if payload.get("codigo_natureza_juridica") is not None
            else None
        ),
        natureza_juridica_descricao=payload.get("natureza_juridica"),
        porte=payload.get("porte"),
        cnae_principal_codigo=(
            str(payload["cnae_fiscal"]) if payload.get("cnae_fiscal") is not None else None
        ),
        cnae_principal_descricao=payload.get("cnae_fiscal_descricao"),
        cnaes_secundarios=cnaes_secundarios,
        logradouro=payload.get("logradouro") or None,
        numero=payload.get("numero") or None,
        complemento=payload.get("complemento") or None,
        bairro=payload.get("bairro") or None,
        municipio=payload.get("municipio") or None,
        uf=payload.get("uf") or None,
        cep=payload.get("cep") or None,
        partners=partners,
        source_provider=source_provider,
        raw_response=payload,
    )
