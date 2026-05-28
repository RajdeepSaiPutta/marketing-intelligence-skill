from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.memory.store import store
from app.security.auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


class CreateAPIKeyRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        cleaned = value.replace("\x00", "").strip()
        if not cleaned:
            raise ValueError("label cannot be empty.")
        return cleaned


@router.post("/keys", dependencies=[Depends(require_admin)])
async def create_api_key(request: CreateAPIKeyRequest):
    raw_key = store.create_api_key(request.label)
    return {
        "api_key": raw_key,
        "detail": "Store this key now. It cannot be retrieved again.",
    }


@router.get("/keys", dependencies=[Depends(require_admin)])
async def list_api_keys():
    return {"keys": store.list_api_keys()}


@router.delete("/keys/{key_hash}", dependencies=[Depends(require_admin)])
async def revoke_api_key(key_hash: str):
    if len(key_hash) != 64:
        raise HTTPException(status_code=422, detail="key_hash must be a SHA-256 hex digest.")
    revoked = store.revoke_api_key(key_hash)
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found.")
    return {"revoked": True}
