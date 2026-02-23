"""Idempotency middleware — prevents duplicate POST/PUT/PATCH requests.

Reads the ``Idempotency-Key`` header and caches responses for a configurable
TTL window.  Duplicate requests within the window receive the cached response.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Protocol, runtime_checkable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger()

IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}
IDEMPOTENCY_HEADER = "Idempotency-Key"
DEFAULT_TTL = 86400  # 24 hours


@runtime_checkable
class IdempotencyStore(Protocol):
    """Protocol for pluggable idempotency backends (e.g. Redis)."""

    async def get(self, key: str) -> dict[str, Any] | None: ...
    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...


class InMemoryIdempotencyStore:
    """Simple in-memory idempotency store with TTL cleanup."""

    def __init__(self, ttl: int = DEFAULT_TTL) -> None:
        self._store: dict[str, tuple[dict[str, Any], float]] = {}
        self._ttl = ttl

    async def get(self, key: str) -> dict[str, Any] | None:
        self._cleanup()
        entry = self._store.get(key)
        if entry is None:
            return None
        data, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return data

    async def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None:
        effective_ttl = ttl if ttl is not None else self._ttl
        self._store[key] = (value, time.monotonic() + effective_ttl)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def _cleanup(self) -> None:
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

    @property
    def size(self) -> int:
        self._cleanup()
        return len(self._store)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that enforces idempotency on mutating requests.

    If a request includes an ``Idempotency-Key`` header, the response is
    cached and replayed on subsequent requests with the same key.
    """

    def __init__(self, app: Any, store: IdempotencyStore | None = None, ttl: int = DEFAULT_TTL):
        super().__init__(app)
        self.store: IdempotencyStore = store or InMemoryIdempotencyStore(ttl=ttl)
        self.ttl = ttl

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in IDEMPOTENT_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get(IDEMPOTENCY_HEADER)
        if not idempotency_key:
            return await call_next(request)

        # Build composite key from method + path + idempotency key
        composite_key = self._build_key(request.method, str(request.url.path), idempotency_key)

        # Check for cached response
        cached = await self.store.get(composite_key)
        if cached is not None:
            logger.info(
                "idempotency_cache_hit",
                key=idempotency_key,
                method=request.method,
                path=request.url.path,
            )
            return JSONResponse(
                content=cached["body"],
                status_code=cached["status_code"],
                headers={"X-Idempotency-Replayed": "true"},
            )

        # Mark key as in-flight to prevent concurrent processing
        await self.store.set(
            composite_key,
            {"status": "processing"},
            ttl=60,  # Short TTL for in-flight marker
        )

        response = await call_next(request)

        # Cache the response
        try:
            body = b""
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                if isinstance(chunk, str):
                    body += chunk.encode()
                else:
                    body += chunk

            body_json = json.loads(body) if body else {}
            await self.store.set(
                composite_key,
                {"body": body_json, "status_code": response.status_code},
                ttl=self.ttl,
            )

            return JSONResponse(
                content=body_json,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
        except (json.JSONDecodeError, Exception):
            # Non-JSON responses — pass through without caching
            await self.store.delete(composite_key)
            return response

    @staticmethod
    def _build_key(method: str, path: str, idempotency_key: str) -> str:
        raw = f"{method}:{path}:{idempotency_key}"
        return hashlib.sha256(raw.encode()).hexdigest()
