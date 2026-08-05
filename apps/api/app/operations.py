from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
import logging
from threading import Lock
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.configuration import Settings


access_logger = logging.getLogger("sportsintel.access")


class FixedWindowRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._counts: dict[tuple[str, str, int], int] = {}
        self._lock = Lock()

    def allow(self, scope: str, client_ip: str, limit: int) -> bool:
        window = int(self._clock() // 60)
        key = (scope, client_ip, window)
        with self._lock:
            self._counts = {
                existing: count
                for existing, count in self._counts.items()
                if existing[2] >= window - 1
            }
            count = self._counts.get(key, 0) + 1
            self._counts[key] = count
            return count <= limit

    def clear(self) -> None:
        with self._lock:
            self._counts.clear()


def _is_health_path(path: str) -> bool:
    return path in {"/health", "/api/sports/nfl/snapshot-store/health"}


def _is_admin_request(method: str, path: str) -> bool:
    return (
        path.startswith("/api/admin")
        or (method == "POST" and path == "/api/sports/nfl/history/clear")
        or (
            method == "DELETE"
            and path.startswith("/api/sports/nfl/")
            and path.endswith("/history")
        )
    )


def _client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.rsplit(",", 1)[-1].strip()
    return request.client.host if request.client else "unknown"


def _security_headers(response: Response, settings: Settings) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    if settings.production:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )


class OperationalMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings: Settings = request.app.state.settings
        limiter: FixedWindowRateLimiter = request.app.state.rate_limiter
        request_id = str(uuid4())
        client_ip = _client_ip(request, settings)
        path = request.url.path
        method = request.method.upper()
        started = time.perf_counter()

        scope = "admin" if _is_admin_request(method, path) else "public"
        limit = (
            settings.admin_rate_limit
            if scope == "admin"
            else settings.public_rate_limit
        )
        allowed = _is_health_path(path) or limiter.allow(scope, client_ip, limit)

        status = 500
        try:
            if allowed:
                response = await call_next(request)
            else:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                )
                response.headers["Retry-After"] = "60"
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            _security_headers(response, settings)
            return response
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            access_logger.info(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "path": path,
                        "status": status,
                        "latency_ms": latency_ms,
                        "client_ip": client_ip,
                        "request_id": request_id,
                    },
                    separators=(",", ":"),
                )
            )
