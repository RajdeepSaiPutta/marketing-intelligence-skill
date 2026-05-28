import logging
import re
import uuid
from pathlib import Path

from app.config import get_settings
from app.memory.store import store

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 500 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}


async def process_upload(filename: str, content: bytes) -> dict:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds 500KB limit.")

    text_content = _extract_text(content, ext)
    text_content = text_content.strip()
    if not text_content:
        raise ValueError("No extractable text found in file.")

    document_id = str(uuid.uuid4())
    store.save_document(
        document_id=document_id,
        filename=filename,
        content_type=ext,
        text_content=text_content,
        char_count=len(text_content),
    )
    return {
        "id": document_id,
        "filename": filename,
        "content_type": ext,
        "char_count": len(text_content),
    }


def list_documents() -> list[dict]:
    return store.list_documents()


def get_document(document_id: str) -> dict | None:
    return store.get_document(document_id)


def get_document_text(document_id: str) -> str | None:
    return store.get_document_text(document_id)


def delete_document(document_id: str) -> bool:
    return store.delete_document(document_id)


def _extract_text(content: bytes, ext: str) -> str:
    if ext == ".pdf":
        return _extract_pdf_text(content)
    return content.decode("utf-8", errors="replace")


def _extract_pdf_text(content: bytes) -> str:
    try:
        import fitz
    except ImportError:
        logger.error("pymupdf not installed, cannot parse PDF")
        return ""
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        parts: list[str] = []
        for page in doc:
            parts.append(page.get_text())
        doc.close()
        text = "\n".join(parts)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception:
        logger.error("PDF extraction failed")
        return ""
