from dataclasses import dataclass

import httpx

from app.providers.base import ProviderError


@dataclass
class GraphRelation:
    cnpj: str
    razao_social: str
    graph_ref_id: str
    nome: str
    cpf_masked: str | None


class GrafoMinhaReceitaProvider:
    """Undocumented companion service to Minha Receita's main CNPJ API.

    Its single endpoint answers "relations for this id", where id may be a
    CNPJ (returns that company's person-partners, each tagged with a stable
    graph_ref_id) or a graph_ref_id (returns every company that person is
    linked to) — the reverse lookup the plain CNPJ-keyed endpoints can't do.
    Same underlying open dataset as Minha Receita, no separate ToS beyond it.
    There is no fallback provider for this specific capability: a failure
    here surfaces as ProviderError and the caller decides whether to skip
    that branch of the graph.
    """

    name = "grafo_minha_receita"

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_relations(self, ref: str) -> list[GraphRelation]:
        url = f"{self._base_url}/{ref}"
        try:
            response = httpx.get(url, timeout=self._timeout_seconds)
        except httpx.HTTPError as exc:
            raise ProviderError(f"grafo_minha_receita request failed: {exc}") from exc

        if response.status_code != 200:
            raise ProviderError(f"grafo_minha_receita returned status {response.status_code}")

        try:
            return [
                GraphRelation(
                    cnpj=item["cnpj"],
                    razao_social=item["razao_social"],
                    graph_ref_id=item["id"],
                    nome=item["nome"],
                    cpf_masked=item.get("cpf"),
                )
                for item in response.json()
            ]
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"grafo_minha_receita returned unexpected shape: {exc}") from exc
