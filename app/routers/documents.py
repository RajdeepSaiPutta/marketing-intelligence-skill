import logging

from fastapi import APIRouter, HTTPException, UploadFile

from app.services.document_service import (
    delete_document,
    get_document,
    get_document_text,
    list_documents,
    process_upload,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("")
async def upload_document(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
    content = await file.read()
    try:
        result = await process_upload(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.error("Document upload failed")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again.")
    return result


@router.get("")
async def list_uploaded_documents():
    return {"documents": list_documents()}


@router.get("/{document_id}")
async def get_document_metadata(document_id: str):
    doc = get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.get("/{document_id}/content")
async def get_document_content(document_id: str):
    text = get_document_text(document_id)
    if text is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"id": document_id, "content": text}


@router.delete("/{document_id}")
async def delete_uploaded_document(document_id: str):
    deleted = delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": True}
