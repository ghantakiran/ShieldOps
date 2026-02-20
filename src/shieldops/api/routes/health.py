"""Health check routes for system dependencies."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request

from shieldops.api.auth.dependencies import require_role
from shieldops.api.auth.models import UserRole
from shieldops.config import settings

logger = structlog.get_logger()

router = APIRouter()

# Track when the process started for uptime calculation
_start_time: float = time.monotonic()

HEALTH_CHECK_TIMEOUT = 2.0  # seconds


def _elapsed_ms(start: float) -> float:
    """Return elapsed milliseconds since *start*."""
    return round((time.monotonic() - start) * 1000, 1)


async def _check_database(
    request: Request,
) -> dict[str, Any]:
    """Check PostgreSQL connectivity via SELECT 1."""
    start = time.monotonic()
    sf = getattr(request.app.state, "session_factory", None)
    if sf is None:
        return {
            "status": "unhealthy",
            "latency_ms": None,
            "error": "Database not configured",
        }

    from sqlalchemy import text

    async with sf() as session:
        result = await session.execute(text("SELECT version()"))
        version_str = result.scalar() or "PostgreSQL"

    return {
        "status": "healthy",
        "latency_ms": _elapsed_ms(start),
        "details": version_str.split(",")[0],
    }


async def _check_redis(
    request: Request,
) -> dict[str, Any]:
    """Ping Redis and return server info."""
    start = time.monotonic()

    import redis.asyncio as aioredis

    r = aioredis.from_url(  # type: ignore[no-untyped-call]
        settings.redis_url,
        socket_connect_timeout=HEALTH_CHECK_TIMEOUT,
    )
    try:
        await r.ping()  # type: ignore[misc]
        info = await r.info("server")
        version = info.get("redis_version", "unknown")
    finally:
        await r.aclose()

    return {
        "status": "healthy",
        "latency_ms": _elapsed_ms(start),
        "details": f"Redis {version}",
    }


async def _check_kafka(
    request: Request,
) -> dict[str, Any]:
    """Check Kafka producer connectivity if available."""
    start = time.monotonic()
    event_bus = getattr(request.app.state, "event_bus", None)
    if event_bus is None:
        return {
            "status": "healthy",
            "latency_ms": None,
            "details": "Kafka not configured (skipped)",
        }

    producer = getattr(event_bus, "producer", None)
    if producer is None:
        return {
            "status": "unhealthy",
            "latency_ms": _elapsed_ms(start),
            "error": "Kafka producer not initialized",
        }

    # AIOKafkaProducer exposes _sender.sender_task
    client = getattr(producer, "_client", None)
    if client is not None:
        connected = getattr(client, "connected", False)
        if not connected:
            return {
                "status": "unhealthy",
                "latency_ms": _elapsed_ms(start),
                "error": "Kafka producer not connected",
            }

    return {
        "status": "healthy",
        "latency_ms": _elapsed_ms(start),
        "details": f"Kafka brokers: {settings.kafka_brokers}",
    }


async def _check_opa(
    request: Request,
) -> dict[str, Any]:
    """HTTP GET to the OPA health endpoint."""
    start = time.monotonic()

    import httpx

    async with httpx.AsyncClient(
        timeout=HEALTH_CHECK_TIMEOUT,
    ) as client:
        resp = await client.get(f"{settings.opa_endpoint}/health")
        if resp.status_code != 200:
            return {
                "status": "unhealthy",
                "latency_ms": _elapsed_ms(start),
                "error": f"OPA returned status {resp.status_code}",
            }

    return {
        "status": "healthy",
        "latency_ms": _elapsed_ms(start),
        "details": f"OPA at {settings.opa_endpoint}",
    }


def _safe_result(
    name: str,
    result: dict[str, Any] | BaseException,
) -> dict[str, Any]:
    """Normalize a gather result — exceptions become unhealthy."""
    if isinstance(result, BaseException):
        return {
            "status": "unhealthy",
            "latency_ms": None,
            "error": f"{type(result).__name__}: {result}",
        }
    return result


@router.get("/health/detailed")
async def detailed_health(
    request: Request,
    _user: Any = Depends(require_role(UserRole.VIEWER, UserRole.OPERATOR, UserRole.ADMIN)),
) -> dict[str, Any]:
    """Check health of all system dependencies.

    Returns per-dependency status with latency, overall
    status, and server uptime.
    """
    check_names = ["database", "redis", "kafka", "opa"]
    check_fns = [
        _check_database,
        _check_redis,
        _check_kafka,
        _check_opa,
    ]

    # Run all checks concurrently with a per-check timeout
    wrapped = [asyncio.wait_for(fn(request), timeout=HEALTH_CHECK_TIMEOUT) for fn in check_fns]
    raw_results = await asyncio.gather(*wrapped, return_exceptions=True)

    checks: dict[str, Any] = {}
    for name, raw in zip(check_names, raw_results, strict=True):
        checks[name] = _safe_result(name, raw)

    # Determine overall status
    db_status = checks["database"]["status"]
    all_statuses = [c["status"] for c in checks.values()]

    if db_status == "unhealthy":
        overall = "unhealthy"
    elif any(s == "unhealthy" for s in all_statuses):
        overall = "degraded"
    else:
        overall = "healthy"

    uptime_seconds = round(time.monotonic() - _start_time, 1)

    return {
        "status": overall,
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
        "uptime_seconds": uptime_seconds,
    }
