import uuid
from typing import Literal

from pydantic import BaseModel

NodeType = Literal["company", "person"]
EdgeType = Literal["partnership", "company_partnership"]


class GraphNodeOut(BaseModel):
    id: uuid.UUID
    node_type: NodeType
    label: str
    cnpj: str | None = None
    situacao_cadastral: str | None = None
    faixa_etaria: str | None = None
    shared_address_company_count: int | None = None


class GraphEdgeOut(BaseModel):
    id: uuid.UUID
    source: uuid.UUID
    target: uuid.UUID
    edge_type: EdgeType
    label: str | None = None


class GraphIndicatorsOut(BaseModel):
    shared_partner_person_ids: list[uuid.UUID]
    shared_address_keys: dict[str, int]


class GraphOut(BaseModel):
    root_cnpj: str
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    indicators: GraphIndicatorsOut


class GraphDeltaOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
