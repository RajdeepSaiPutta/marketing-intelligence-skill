from dataclasses import dataclass

from fastapi import Header, HTTPException

from app.config import get_settings
from app.memory.store import store


@dataclass(frozen=True)
class AuthContext:
    is_authenticated: bool
    identifier: str
    label: str = ""


def parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization header.")
    return token.strip()


def authenticate_request(authorization: str | None, client_host: str) -> AuthContext:
    token = parse_bearer_token(authorization)
    if token is None:
        return AuthContext(is_authenticated=False, identifier=f"anon:{client_host}")

    api_key = store.validate_api_key(token)
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    return AuthContext(
        is_authenticated=True,
        identifier=f"key:{api_key['key_hash']}",
        label=api_key["label"] or "",
    )


async def require_admin(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Admin API key is not configured.")

    token = parse_bearer_token(authorization)
    if token != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Admin API key is required.")
