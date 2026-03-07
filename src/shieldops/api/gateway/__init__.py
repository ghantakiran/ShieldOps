"""API Gateway — tenant-aware routing, key management, rate limiting."""

from __future__ import annotations

from shieldops.api.gateway.key_manager import APIKeyManager
from shieldops.api.gateway.middleware import APIGatewayMiddleware
from shieldops.api.gateway.models import (
    APIKey,
    APIKeyScope,
    APIKeyStatus,
    APIUsageRecord,
    TenantConfig,
)
from shieldops.api.gateway.rate_limiter import TenantRateLimiter

__all__ = [
    "APIGatewayMiddleware",
    "APIKey",
    "APIKeyManager",
    "APIKeyScope",
    "APIKeyStatus",
    "APIUsageRecord",
    "TenantConfig",
    "TenantRateLimiter",
]
