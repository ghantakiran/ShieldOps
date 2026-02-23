"""Circuit breaker API routes."""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status

from shieldops.utils.circuit_breaker import CircuitBreakerRegistry

logger = structlog.get_logger()
router = APIRouter(prefix="/circuit-breakers", tags=["Circuit Breakers"])

_registry: CircuitBreakerRegistry | None = None


def set_registry(registry: CircuitBreakerRegistry) -> None:
    global _registry
    _registry = registry


def _get_registry() -> CircuitBreakerRegistry:
    if _registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Circuit breaker registry not initialized",
        )
    return _registry


@router.get("")
async def list_circuit_breakers() -> dict[str, Any]:
    """Get all circuit breaker states."""
    registry = _get_registry()
    stats = registry.all_stats()
    return {
        "breakers": [s.model_dump() for s in stats],
        "total": len(stats),
    }


@router.post("/{name}/reset")
async def reset_circuit_breaker(name: str) -> dict[str, Any]:
    """Force-reset a circuit breaker to CLOSED state."""
    registry = _get_registry()
    success = await registry.reset(name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker '{name}' not found",
        )
    return {"name": name, "status": "reset", "state": "closed"}
