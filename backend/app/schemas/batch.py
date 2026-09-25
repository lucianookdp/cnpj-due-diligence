import uuid
from datetime import datetime

from pydantic import BaseModel, Field

MAX_BATCH_SIZE = 50


class BatchCheckCreate(BaseModel):
    # The browser extracts these from the user's file; the file itself never
    # reaches the server.
    cnpjs: list[str] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class BatchCheckItemOut(BaseModel):
    cnpj: str
    status: str
    score: int | None
    razao_social: str | None
    situacao_cadastral: str | None
    flags: list[str]


class BatchCheckOut(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime
    items: list[BatchCheckItemOut]
