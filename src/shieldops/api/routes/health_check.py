"""Unified deep health check routes for all platform components.

These endpoints are unauthenticated — they are consumed by Kubernetes
probes, load balancers, and external monitoring systems.
"""

from __future__ import annotations

import random
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException

from shieldops.api.routes.health_models import (
    ComponentHealth,
    DeepHealthResponse,
    HealthStatus,
)

logger = structlog.get_logger()

router = APIRouter(tags=["health"])

# Process start time — used for uptime calculation.
_start_time: float = time.monotonic()

_PLATFORM_VERSION = "0.1.0"

# Components recognised by the /components/{component} endpoint.
KNOWN_COMPONENTS: set[str] = {
    "database",
    "redis",
    "kafka",
    "opa",
    "aws",
    "gcp",
    "azure",
    "kubernetes",
    "pipeline",
    "gateway",
}


# ---------------------------------------------------------------------------
# Mock component checkers
# ---------------------------------------------------------------------------
# In production each function would actually ping the service.  For now they
# return realistic mock data with one component intentionally *degraded* so
# dashboards and alerting can be validated.


async def _check_component(name: str) -> ComponentHealth:
    """Return a mock health result for *name*.

    The ``kafka`` component is deliberately reported as *degraded* to
    exercise downstream handling of non-healthy states.
    """
    # Simulate variable latency per component type.
    rng = random.Random()  # noqa: S311
    latency_map: dict[str, float] = {
        "database": round(rng.uniform(1.0, 5.0), 2),
        "redis": round(rng.uniform(0.3, 1.5), 2),
        "kafka": round(rng.uniform(8.0, 25.0), 2),
        "opa": round(rng.uniform(1.5, 4.0), 2),
        "aws": round(rng.uniform(30.0, 80.0), 2),
        "gcp": round(rng.uniform(25.0, 70.0), 2),
        "azure": round(rng.uniform(35.0, 90.0), 2),
        "kubernetes": round(rng.uniform(2.0, 8.0), 2),
        "pipeline": round(rng.uniform(1.0, 3.0), 2),
        "gateway": round(rng.uniform(0.5, 2.0), 2),
    }

    details_map: dict[str, dict[str, Any]] = {
        "database": {"engine": "PostgreSQL 16.2", "connections": 12},
        "redis": {"version": "7.2.4", "connected_clients": 8},
        "kafka": {
            "brokers": 3,
            "topic_partitions": 24,
            "consumer_lag": 1542,
        },
        "opa": {"version": "0.62.0", "policies_loaded": 47},
        "aws": {"region": "us-east-1", "sts_identity": "arn:aws:iam::role/shieldops"},
        "gcp": {"project": "shieldops-prod", "region": "us-central1"},
        "azure": {
            "subscription": "shieldops-prod",
            "region": "eastus",
        },
        "kubernetes": {
            "cluster": "shieldops-prod",
            "nodes_ready": 6,
            "api_server": "reachable",
        },
        "pipeline": {"active_runs": 3, "queued": 1},
        "gateway": {"uptime_hours": 720.5, "routes_registered": 184},
    }

    # Kafka is intentionally degraded for demonstration purposes.
    if name == "kafka":
        status = HealthStatus.degraded
        error: str | None = "Consumer lag above threshold (1542 > 1000)"
    else:
        status = HealthStatus.healthy
        error = None

    latency = latency_map.get(name, round(rng.uniform(1.0, 10.0), 2))
    details = details_map.get(name, {})

    await logger.adebug(
        "health_check_component",
        component=name,
        status=status.value,
        latency_ms=latency,
    )

    return ComponentHealth(
        name=name,
        status=status,
        latency_ms=latency,
        last_check=datetime.now(UTC),
        details=details,
        error=error,
    )


def _overall_status(
    components: list[ComponentHealth],
) -> HealthStatus:
    """Derive overall platform status from individual component statuses.

    Rules:
    * Any *unhealthy* component -> overall **unhealthy**
    * Any *degraded* component  -> overall **degraded**
    * Otherwise                -> overall **healthy**
    """
    statuses = {c.status for c in components}
    if HealthStatus.unhealthy in statuses:
        return HealthStatus.unhealthy
    if HealthStatus.degraded in statuses:
        return HealthStatus.degraded
    return HealthStatus.healthy


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/health/deep",
    response_model=DeepHealthResponse,
    summary="Deep health check across all platform components",
)
async def deep_health() -> DeepHealthResponse:
    """Run health checks against every registered component and return an
    aggregated report including per-component status, latencies, and uptime.
    """
    components: list[ComponentHealth] = []
    for name in sorted(KNOWN_COMPONENTS):
        result = await _check_component(name)
        components.append(result)

    status = _overall_status(components)
    uptime = round(time.monotonic() - _start_time, 1)

    await logger.ainfo(
        "deep_health_check",
        status=status.value,
        component_count=len(components),
        uptime_seconds=uptime,
    )

    return DeepHealthResponse(
        status=status,
        components=components,
        uptime_seconds=uptime,
        version=_PLATFORM_VERSION,
        checked_at=datetime.now(UTC),
    )


@router.get(
    "/health/components/{component}",
    response_model=ComponentHealth,
    summary="Health status for a specific component",
)
async def component_health(component: str) -> ComponentHealth:
    """Return health information for *component*.

    Raises 404 if the component name is not recognised.
    """
    if component not in KNOWN_COMPONENTS:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown component '{component}'. Valid: {', '.join(sorted(KNOWN_COMPONENTS))}"
            ),
        )

    return await _check_component(component)


@router.get(
    "/health/readiness",
    summary="Kubernetes readiness probe",
)
async def readiness() -> dict[str, Any]:
    """Readiness probe — verifies that critical dependencies (database,
    redis) are reachable.  Returns 503 if any critical component is
    unhealthy.
    """
    critical = ["database", "redis"]
    results: list[ComponentHealth] = []
    for name in critical:
        results.append(await _check_component(name))

    all_ok = all(r.status in {HealthStatus.healthy, HealthStatus.degraded} for r in results)

    if not all_ok:
        raise HTTPException(
            status_code=503,
            detail="One or more critical dependencies are unhealthy",
        )

    return {
        "status": "ready",
        "checked_at": datetime.now(UTC).isoformat(),
        "components": {r.name: r.status.value for r in results},
    }


@router.get(
    "/health/liveness",
    summary="Kubernetes liveness probe",
)
async def liveness() -> dict[str, Any]:
    """Liveness probe — confirms the process is alive and able to serve
    requests.  This endpoint performs no external I/O.
    """
    return {
        "status": "alive",
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
        "checked_at": datetime.now(UTC).isoformat(),
    }
