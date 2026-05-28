import json
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from starlette.types import Receive, Scope, Send

from app.config import get_settings
from app.memory.store import estimate_tokens, now_utc, store
from app.security.auth import authenticate_request


class RateLimitMiddleware:
    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._should_limit(scope):
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }
        client_host = self._client_host(scope)
        try:
            auth_context = authenticate_request(headers.get("authorization"), client_host)
        except HTTPException as exc:
            await self._send_json(send, exc.status_code, {"detail": exc.detail})
            return

        content_length = int(headers.get("content-length", "0") or "0")
        estimated_tokens = estimate_tokens("x" * content_length)
        settings = get_settings()
        now = now_utc()

        scoped_limits = (
            (
                "client_minute",
                auth_context.identifier,
                now - timedelta(minutes=1),
                settings.authenticated_requests_per_minute
                if auth_context.is_authenticated
                else settings.anonymous_requests_per_minute,
                60,
            ),
            (
                "client_day",
                auth_context.identifier,
                now - timedelta(days=1),
                settings.authenticated_requests_per_day
                if auth_context.is_authenticated
                else settings.anonymous_requests_per_day,
                86_400,
            ),
            ("global_minute", "all", now - timedelta(minutes=1), settings.global_requests_per_minute, 60),
            ("global_day", "all", now - timedelta(days=1), settings.global_requests_per_day, 86_400),
        )

        for scope_name, identifier, since, limit, retry_after in scoped_limits:
            count = store.count_rate_events(scope_name, identifier, since)
            if count >= limit:
                await self._send_json(
                    send,
                    429,
                    {
                        "error": "rate_limit_exceeded",
                        "detail": "Rate limit reached. Please retry later.",
                        "retry_after": retry_after,
                    },
                    headers=[(b"retry-after", str(retry_after).encode("latin1"))],
                )
                return

        endpoint = scope.get("path", "")
        for scope_name, identifier, *_ in scoped_limits:
            store.record_rate_event(scope_name, identifier, endpoint, estimated_tokens)

        await self.app(scope, receive, send)

    def _should_limit(self, scope: Scope) -> bool:
        if scope["type"] != "http":
            return False
        path = scope.get("path", "")
        method = scope.get("method", "")
        if method == "OPTIONS":
            return False
        limited_paths = {
            "/api/chat",
            "/api/generate-content",
            "/api/generate-content-stream",
            "/api/score-article",
        }
        return path in limited_paths and method in {"POST", "PUT", "PATCH", "DELETE"}

    def _client_host(self, scope: Scope) -> str:
        client = scope.get("client")
        if not client:
            return "unknown"
        return str(client[0])

    async def _send_json(
        self,
        send: Send,
        status_code: int,
        payload: dict[str, Any],
        headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        response_headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("latin1")),
        ]
        if headers:
            response_headers.extend(headers)
        await send({"type": "http.response.start", "status": status_code, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})
