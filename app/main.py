import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.types import Receive, Scope, Send

from app.config import get_settings
from app.routers import admin, chat, documents as documents_router, generate, score, sessions
from app.security.cors import configure_cors
from app.security.rate_limiter import RateLimitMiddleware

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Optimized Groq & Google Grounding Engine")
    application.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    application.add_middleware(RateLimitMiddleware)
    configure_cors(application, settings)
    register_exception_handlers(application)
    application.include_router(admin.router)
    application.include_router(chat.router)
    application.include_router(documents_router.router)
    application.include_router(generate.router)
    application.include_router(score.router)
    application.include_router(sessions.router)

    @application.get("/", include_in_schema=False)
    async def serve_index():
        content = Path("index.html").read_text(encoding="utf-8")
        return HTMLResponse(content)

    return application


class BodySizeLimitMiddleware:
    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]], max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }
        content_length = headers.get("content-length")
        if content_length and not content_length.isdigit():
            await self._send_json(send, 400, {"error": "bad_request", "detail": "Invalid Content-Length header."})
            return
        if content_length is None and scope.get("method") in {"POST", "PUT", "PATCH"}:
            await self._send_json(
                send,
                411,
                {"error": "length_required", "detail": "Content-Length header is required."},
            )
            return
        if content_length and int(content_length) > self.max_bytes:
            await self._send_json(
                send,
                413,
                {"error": "request_too_large", "detail": "Request body exceeds 1MB."},
            )
            return

        await self.app(scope, receive, send)

    async def _send_json(self, send: Send, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning("Request validation failed at %s", request.url.path)
        return JSONResponse(
            status_code=422,
            content={
                "error": "request_validation_failed",
                "detail": "Invalid request body.",
            },
        )

    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code >= 500:
            detail = "An internal error occurred. Please try again."
        else:
            detail = exc.detail if isinstance(exc.detail, str) else "Request rejected."
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled application error at %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal error occurred. Please try again."},
        )


app = create_app()
