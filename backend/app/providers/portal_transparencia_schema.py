"""Parsing for Portal da Transparência's api-de-dados JSON records.

CEIS and CNEP share one shape (sancionado + pessoa + tipoSancao); CEPIM and
Acordos de Leniência each have their own. A leniência record can sanction
multiple companies at once (its `sancoes` array), so its parser returns a
list instead of a single entry.
"""

import logging
import re
from datetime import date, datetime

from app.core.document import InvalidDocumentError, normalize_document
from app.repositories.restrictive_list_repository import RawRestrictiveListEntry

logger = logging.getLogger(__name__)

# The source API leaks literal "%uXXXX"/"%UXXXX" tokens for some punctuation
# (JS-style legacy escape() output that never got decoded server-side) —
# e.g. "LTDA %U2013 ME" instead of "LTDA – ME". Decoded for display only;
# raw_data keeps the untouched original for audit.
_JS_UNICODE_ESCAPE_RE = re.compile(r"%[uU]([0-9a-fA-F]{4})")


def _clean_name(value: str | None) -> str:
    if not value:
        return ""
    return _JS_UNICODE_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), value)


def _parse_br_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()  # noqa: DTZ007 (date-only, no tz to attach)
    except ValueError:
        return None


def _document_from(raw_code: str | None) -> tuple[str, str] | None:
    if not raw_code:
        return None
    try:
        return normalize_document(raw_code)
    except InvalidDocumentError:
        logger.warning("could not normalize document %r from restrictive list record", raw_code)
        return None


def parse_ceis_record(record: dict) -> RawRestrictiveListEntry | None:
    return _parse_ceis_or_cnep(record, list_type="ceis")


def parse_cnep_record(record: dict) -> RawRestrictiveListEntry | None:
    return _parse_ceis_or_cnep(record, list_type="cnep")


def _parse_ceis_or_cnep(record: dict, list_type: str) -> RawRestrictiveListEntry | None:
    sancionado = record.get("sancionado") or {}
    document = _document_from(sancionado.get("codigoFormatado"))
    if document is None:
        return None
    doc, doc_type = document

    tipo_sancao = record.get("tipoSancao") or {}
    orgao = record.get("orgaoSancionador") or {}

    return RawRestrictiveListEntry(
        list_type=list_type,
        external_id=str(record["id"]),
        document=doc,
        document_type=doc_type,
        name=_clean_name(sancionado.get("nome")),
        reason=tipo_sancao.get("descricaoResumida"),
        source_org=orgao.get("nome"),
        sanction_start_date=_parse_br_date(record.get("dataInicioSancao")),
        sanction_end_date=_parse_br_date(record.get("dataFimSancao")),
        raw_data=record,
    )


def parse_cepim_record(record: dict) -> RawRestrictiveListEntry | None:
    pessoa = record.get("pessoaJuridica") or {}
    document = _document_from(pessoa.get("cnpjFormatado") or pessoa.get("cpfFormatado"))
    if document is None:
        return None
    doc, doc_type = document

    orgao = record.get("orgaoSuperior") or {}

    return RawRestrictiveListEntry(
        list_type="cepim",
        external_id=str(record["id"]),
        document=doc,
        document_type=doc_type,
        name=_clean_name(pessoa.get("nome") or pessoa.get("razaoSocialReceita")),
        reason=record.get("motivo"),
        source_org=orgao.get("nome"),
        sanction_start_date=None,
        sanction_end_date=None,
        raw_data=record,
    )


def parse_leniencia_record(record: dict) -> list[RawRestrictiveListEntry]:
    entries = []
    agreement_id = record["id"]
    situacao = record.get("situacaoAcordo")
    orgao = record.get("orgaoResponsavel")
    start = _parse_br_date(record.get("dataInicioAcordo"))
    end = _parse_br_date(record.get("dataFimAcordo"))

    for i, empresa in enumerate(record.get("sancoes") or []):
        document = _document_from(empresa.get("cnpjFormatado") or empresa.get("cnpj"))
        if document is None:
            continue
        doc, doc_type = document
        entries.append(
            RawRestrictiveListEntry(
                list_type="leniencia",
                external_id=f"{agreement_id}:{i}",
                document=doc,
                document_type=doc_type,
                name=_clean_name(
                    empresa.get("razaoSocial") or empresa.get("nomeInformadoOrgaoResponsavel")
                ),
                reason=situacao,
                source_org=orgao,
                sanction_start_date=start,
                sanction_end_date=end,
                raw_data=record,
            )
        )
    return entries
