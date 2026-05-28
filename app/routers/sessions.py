import uuid

from fastapi import APIRouter, HTTPException, Query

from app.services.session_service import session_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return {"sessions": session_service.list_sessions(limit=limit, offset=offset)}


@router.get("/{session_id}")
async def get_session(session_id: str):
    clean_session_id = validate_session_id(session_id)
    session = session_service.get_session(clean_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.post("/{session_id}/resume")
async def resume_session(session_id: str):
    clean_session_id = validate_session_id(session_id)
    session = session_service.get_session(clean_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    clean_session_id = validate_session_id(session_id)
    deleted = session_service.delete_session(clean_session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"deleted": True}


def validate_session_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="session_id must be a valid UUID.") from exc
