import re
from typing import Literal

DocumentType = Literal["cnpj", "cpf"]

_DIGITS_ONLY = re.compile(r"\D")


class InvalidDocumentError(ValueError):
    pass


def normalize_document(raw: str) -> tuple[str, DocumentType]:
    """Strips punctuation and classifies by digit count (11 = CPF, 14 = CNPJ)."""
    digits = _DIGITS_ONLY.sub("", raw)
    if len(digits) == 11:
        return digits, "cpf"
    if len(digits) == 14:
        return digits, "cnpj"
    raise InvalidDocumentError(f"expected 11 (CPF) or 14 (CNPJ) digits, got {len(digits)}: {raw!r}")


def mask_cpf(cpf_digits: str) -> str:
    """Reproduces Receita's own CPF masking (first 3 and last 2 digits hidden).

    Used to compare a full CPF from a restrictive list against the
    already-masked CPF Receita gives us for a sócio — see
    app/services/restrictive_list_matching.py.
    """
    if len(cpf_digits) != 11:
        raise InvalidDocumentError(f"expected 11 CPF digits, got {len(cpf_digits)}: {cpf_digits!r}")
    return f"***{cpf_digits[3:9]}**"
