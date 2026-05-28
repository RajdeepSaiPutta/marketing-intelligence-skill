import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models import ChatRequest
from app.services.chat_service import prepare_chat_request, stream_chat_events

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        prepared = prepare_chat_request(request)
    except HTTPException:
        raise
    except Exception:
        logger.error("Failed to prepare chat request")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again.",
        ) from None

    return StreamingResponse(stream_chat_events(prepared), media_type="text/event-stream")
