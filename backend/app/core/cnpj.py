import re

_DIGITS_ONLY = re.compile(r"\D")


class InvalidCnpjError(ValueError):
    pass


def normalize_cnpj(raw: str) -> str:
    """Strips punctuation and validates the result is 14 digits.

    Does not validate the CNPJ check digits — an invalid-but-well-formed CNPJ
    is simply reported as not found by the provider.
    """
    digits = _DIGITS_ONLY.sub("", raw)
    if len(digits) != 14:
        raise InvalidCnpjError(f"CNPJ deve ter 14 dígitos, recebido {len(digits)}: {raw!r}")
    return digits
