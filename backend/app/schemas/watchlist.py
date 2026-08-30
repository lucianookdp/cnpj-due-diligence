import uuid
from datetime import datetime

from pydantic import BaseModel


class WatchlistEntryCreate(BaseModel):
    cnpj: str
    label: str | None = None


class AlertOut(BaseModel):
    alert_type: str
    message: str
    detected_at: datetime


class WatchlistEntryOut(BaseModel):
    id: uuid.UUID
    cnpj: str
    label: str | None
    created_at: datetime
    razao_social: str | None
    situacao_cadastral: str | None
    recent_alerts: list[AlertOut]
