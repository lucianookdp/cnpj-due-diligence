import uuid

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.security import decode_access_token
from app.models import User
from app.providers.grafo_minha_receita import GrafoMinhaReceitaProvider
from app.providers.resolver import ProviderResolver, build_default_resolver
from app.repositories import user_repository

_bearer_scheme = HTTPBearer()


def get_resolver(settings: Settings = Depends(get_settings)) -> ProviderResolver:
    return build_default_resolver(settings)


def get_grafo_provider(settings: Settings = Depends(get_settings)) -> GrafoMinhaReceitaProvider:
    return GrafoMinhaReceitaProvider(
        settings.grafo_minha_receita_base_url, settings.provider_timeout_seconds
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    user_id = decode_access_token(credentials.credentials, settings.secret_key)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    user = user_repository.get_by_id(db, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user
