import io

import httpx
import pdfplumber

from app.providers.base import ProviderError


class ListaSujaProvider:
    """Downloads and table-extracts the MTE "Cadastro de Empregadores" PDF.

    No JSON/CSV alternative exists for this list (unlike CEIS/CNEP/CEPIM) —
    it's published as a PDF, updated a few times a year.
    """

    name = "lista_suja"

    def __init__(self, pdf_url: str, timeout_seconds: float) -> None:
        self._pdf_url = pdf_url
        self._timeout_seconds = timeout_seconds

    def fetch_raw_rows(self) -> list[list[str | None]]:
        try:
            response = httpx.get(
                self._pdf_url, timeout=self._timeout_seconds, follow_redirects=True
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"lista_suja request failed: {exc}") from exc
        if response.status_code != 200:
            raise ProviderError(f"lista_suja returned status {response.status_code}")

        rows: list[list[str | None]] = []
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    rows.extend(table)
        return rows
