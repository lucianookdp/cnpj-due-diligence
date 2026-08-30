"""Parsing for the MTE "lista suja" PDF table rows (already extracted by pdfplumber).

Two quirks specific to this source, found by inspecting a real extraction:
- For a CNPJ-holder row, the "Empregador" cell repeats the 8-digit CNPJ raiz
  as a prefix before the name (e.g. "41.297.068 GILBERTO ELENO..."), which we
  strip back off.
- A handful of rows carry footnote markers like "(*1)" referencing a legal
  note printed at the end of the document; stripped as cosmetic noise.
"""

import re
from datetime import date, datetime

from app.core.document import InvalidDocumentError, normalize_document
from app.repositories.restrictive_list_repository import RawRestrictiveListEntry

_FOOTNOTE_RE = re.compile(r"\s*\(\*\d+(?:,\s*\*\d+)*\)\s*$")


def _clean_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def _strip_cnpj_prefix(name: str, cnpj_digits: str) -> str:
    prefix = f"{cnpj_digits[0:2]}.{cnpj_digits[2:5]}.{cnpj_digits[5:8]}"
    if name.startswith(prefix):
        return name[len(prefix) :].strip()
    return name


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()  # noqa: DTZ007 (date-only, no tz to attach)
    except ValueError:
        return None


def parse_row(row: list[str | None]) -> RawRestrictiveListEntry | None:
    """row: [ID, Ano, UF, Empregador, CNPJ/CPF, Estabelecimento, Trabalhadores,
    CNAE, Decisão administrativa, Inclusão no Cadastro] — a title/header/
    continuation row (non-numeric ID, or missing document) returns None.
    """
    if len(row) < 9:
        return None

    external_id = (row[0] or "").strip()
    if not external_id.isdigit():
        return None

    try:
        doc, doc_type = normalize_document(row[4] or "")
    except InvalidDocumentError:
        return None

    name = _FOOTNOTE_RE.sub("", _clean_whitespace(row[3]))
    if doc_type == "cnpj":
        name = _strip_cnpj_prefix(name, doc)

    return RawRestrictiveListEntry(
        list_type="trabalho_escravo",
        external_id=external_id,
        document=doc,
        document_type=doc_type,
        name=name,
        reason="Submissão de trabalhadores a condições análogas às de escravo",
        source_org="Ministério do Trabalho e Emprego",
        sanction_start_date=_parse_date(row[8] if len(row) > 8 else None),
        sanction_end_date=None,
        raw_data={"row": row},
    )
